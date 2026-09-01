// 对话视图：消息气泡列表（用户右、助手左，助手气泡走 markdown 渲染），
// 工具卡片按会话原位插入，滚动自动跟随最新消息。
// Chat view: the message bubble list (user right, assistant left; assistant
// bubbles render markdown), tool cards inserted in place, with auto-scroll
// following the latest message.

import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Button, Spin, Typography } from "antd";
import { BulbOutlined } from "@ant-design/icons";
import type { ChatItem } from "./chatModel";
import { ToolCardView } from "./ToolCardView";
import { useTranslation } from "../i18n";

const { Text } = Typography;

/// 思考块（CONTEXT.md 术语）：流式接收、默认折叠，点击展开全文
/// （ADR 0026 决策 4：与工具卡片同一条时间线，不分设侧面板）。
function ThinkingBlock({ text }: { text: string }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  return (
    <div style={{ margin: "4px 0", maxWidth: "92%" }}>
      <Button
        type="text"
        size="small"
        icon={<BulbOutlined />}
        onClick={() => setOpen((o) => !o)}
        style={{ padding: "0 4px", fontSize: 12, color: "var(--tod-text-secondary, #8c8c8c)" }}
      >
        {t("assistant.thinking.title")}
      </Button>
      {open && (
        <div
          style={{
            margin: "2px 0 4px 6px",
            padding: "2px 0 2px 8px",
            borderLeft: "2px solid rgba(128,128,128,0.35)",
            color: "var(--tod-text-secondary, #8c8c8c)",
            fontSize: 12,
            lineHeight: 1.55,
            whiteSpace: "pre-wrap",
            wordBreak: "break-word",
          }}
        >
          {text}
        </div>
      )}
    </div>
  );
}

// 本仓无全局样式表（全内联 + antd），markdown 元素经 components 映射内联样式。
// remark-gfm 启用 GFM 扩展（表格/删除线/任务列表）——助手输出的参数对比表
// 是管道表语法，没有该插件只会显示原始管道文本。
// The repo has no global stylesheet (all inline + antd), so markdown elements
// get inline styles via the components mapping. remark-gfm enables GFM
// extensions (tables/strikethrough/task lists) — the assistant's parameter
// tables use pipe syntax, which renders as raw pipes without the plugin.
const mdComponents = {
  p: ({ children }: any) => <p style={{ margin: "4px 0" }}>{children}</p>,
  code: ({ children, className }: any) =>
    className ? ( //  fenced code block 内的 code 由 pre 管
      <code className={className} style={{ fontSize: 12 }}>{children}</code>
    ) : (
      <code
        style={{
          fontSize: 12,
          background: "rgba(128,128,128,0.18)",
          padding: "0 4px",
          borderRadius: 3,
        }}
      >
        {children}
      </code>
    ),
  pre: ({ children }: any) => (
    <pre
      style={{
        margin: "6px 0",
        padding: 8,
        fontSize: 12,
        overflow: "auto",
        background: "rgba(128,128,128,0.14)",
        borderRadius: 4,
      }}
    >
      {children}
    </pre>
  ),
  ul: ({ children }: any) => <ul style={{ margin: "4px 0", paddingLeft: 20 }}>{children}</ul>,
  ol: ({ children }: any) => <ol style={{ margin: "4px 0", paddingLeft: 20 }}>{children}</ol>,
  a: ({ children, href }: any) => (
    <a href={href} target="_blank" rel="noreferrer" style={{ color: "#0958d9" }}>
      {children}
    </a>
  ),
  // GFM 表格：边栏较窄，块级横向滚动兜底
  // GFM tables: the sidebar is narrow — block-level horizontal scroll as fallback.
  table: ({ children }: any) => (
    <table
      style={{
        borderCollapse: "collapse",
        margin: "6px 0",
        fontSize: 12,
        display: "block",
        maxWidth: "100%",
        overflowX: "auto",
      }}
    >
      {children}
    </table>
  ),
  th: ({ children }: any) => (
    <th
      style={{
        border: "1px solid rgba(128,128,128,0.45)",
        padding: "3px 8px",
        background: "rgba(128,128,128,0.12)",
        textAlign: "left",
        fontWeight: 600,
        whiteSpace: "nowrap",
      }}
    >
      {children}
    </th>
  ),
  td: ({ children }: any) => (
    <td style={{ border: "1px solid rgba(128,128,128,0.45)", padding: "3px 8px" }}>
      {children}
    </td>
  ),
};

export function ChatView({
  items,
  running,
  onOpenRecord,
  onApplyScenario,
}: {
  items: ChatItem[];
  /** 整轮对话进行中（输入禁用 + 顶部"运行中"提示） */
  running: boolean;
  onOpenRecord: (recordId: string, tool: string) => void;
  /** 应用情景（ADR 0027）：scenario_write 完成卡片 → App 打开该情景文件 */
  /** Apply scenario (ADR 0027): a completed scenario_write card → App opens
   *  that scenario file. */
  onApplyScenario?: (path: string) => void;
}) {
  const { t } = useTranslation();
  const bottomRef = useRef<HTMLDivElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  // 贴底才自动跟随（#450）：用户上翻看历史时不被流式增量拽回底部；
  // 初值 true（首屏贴底）。阈值 32px。jsdom 无布局量测（恒 0 → 恒贴底），
  // 非贴底路径以手工验证兜底（规格测试决策注明）。
  // Follow the stream only when stuck to the bottom (#450): streaming deltas
  // no longer yank the user back while reading history; initial true. 32px
  // threshold. jsdom has no layout metrics (always 0 → stuck), the not-stuck
  // path is covered by manual verification (spec testing decisions).
  const stickToBottomRef = useRef(true);
  const handleScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    stickToBottomRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 32;
  };

  // 新内容出现时按贴底状态决定是否滚底；用户消息（末项）无条件滚——
  // 自己刚说的话必须可见（#450）。
  // Scroll to bottom on new content only when stuck; a user message (the last
  // item) always scrolls — one's own words must be visible (#450).
  useEffect(() => {
    const last = items[items.length - 1];
    if (stickToBottomRef.current || last?.kind === "user") {
      bottomRef.current?.scrollIntoView({ behavior: "auto", block: "end" });
    }
  }, [items]);

  return (
    <div ref={scrollRef} onScroll={handleScroll} style={{ flex: 1, overflowY: "auto", minHeight: 0, padding: "4px 2px" }}>
      {items.map((item, idx) => {
        if (item.kind === "user") {
          return (
            <div key={idx} style={{ display: "flex", justifyContent: "flex-end", margin: "6px 0" }}>
              <div
                style={{
                  maxWidth: "88%",
                  padding: "6px 10px",
                  borderRadius: 6,
                  background: "var(--tod-user-bubble, #0958d9)",
                  color: "#fff",
                  fontSize: 13,
                  whiteSpace: "pre-wrap",
                  wordBreak: "break-word",
                }}
              >
                {item.text}
              </div>
            </div>
          );
        }
        if (item.kind === "assistant") {
          return (
            <div key={idx} style={{ display: "flex", justifyContent: "flex-start", margin: "6px 0" }}>
              <div
                style={{
                  maxWidth: "92%",
                  padding: "4px 10px",
                  borderRadius: 6,
                  background: "var(--tod-assistant-bubble, rgba(128,128,128,0.10))",
                  fontSize: 13,
                  lineHeight: 1.55,
                  wordBreak: "break-word",
                }}
              >
                <ReactMarkdown remarkPlugins={[remarkGfm]} components={mdComponents}>
                  {item.text}
                </ReactMarkdown>
              </div>
            </div>
          );
        }
        if (item.kind === "thinking") {
          return <ThinkingBlock key={idx} text={item.text} />;
        }
        if (item.kind === "interrupted") {
          // 中断界限（#453）：居中虚线分隔 + 文案，与 error 气泡区分
          // Interrupt boundary (#453): a centered dashed divider + label,
          // distinct from error bubbles.
          return (
            <div
              key={idx}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                margin: "8px 4px",
                color: "var(--tod-text-secondary, #8c8c8c)",
                fontSize: 11,
              }}
            >
              <span style={{ flex: 1, borderTop: "1px dashed rgba(128, 128, 128, 0.4)" }} />
              {t("assistant.interrupted")}
              <span style={{ flex: 1, borderTop: "1px dashed rgba(128, 128, 128, 0.4)" }} />
            </div>
          );
        }
        if (item.kind === "error") {
          return (
            <div key={idx} style={{ display: "flex", justifyContent: "flex-start", margin: "6px 0" }}>
              <div
                style={{
                  maxWidth: "92%",
                  padding: "6px 10px",
                  borderRadius: 6,
                  border: "1px solid #ff4d4f",
                  color: "#ff4d4f",
                  fontSize: 12,
                  whiteSpace: "pre-wrap",
                  wordBreak: "break-word",
                }}
              >
                {item.text}
              </div>
            </div>
          );
        }
        return (
          <ToolCardView key={item.card.callId} card={item.card} onOpenRecord={onOpenRecord} onApplyScenario={onApplyScenario} />
        );
      })}
      {running && (
        // 生成中指示（#450）：替代静态省略号；Spin 是平面指示器，符合 ADR 0020
        // Generating indicator (#450): replaces the static ellipsis; Spin is a
        // flat indicator, in line with ADR 0020.
        <div style={{ display: "flex", alignItems: "center", gap: 6, margin: "4px 6px" }}>
          <Spin size="small" />
          <Text type="secondary" style={{ fontSize: 11 }}>
            {t("assistant.generating")}
          </Text>
        </div>
      )}
      <div ref={bottomRef} />
    </div>
  );
}
