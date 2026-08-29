// 对话视图：消息气泡列表（用户右、助手左，助手气泡走 markdown 渲染），
// 工具卡片按会话原位插入，滚动自动跟随最新消息。
// Chat view: the message bubble list (user right, assistant left; assistant
// bubbles render markdown), tool cards inserted in place, with auto-scroll
// following the latest message.

import { useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Typography } from "antd";
import type { ChatItem } from "./chatModel";
import { ToolCardView } from "./ToolCardView";

const { Text } = Typography;

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
}: {
  items: ChatItem[];
  /** 整轮对话进行中（输入禁用 + 顶部"运行中"提示） */
  running: boolean;
  onOpenRecord: (recordId: string, tool: string) => void;
}) {
  const bottomRef = useRef<HTMLDivElement>(null);

  // 新内容出现时滚到底部（流式增量与工具卡片都触发）
  // Scroll to the bottom when new content appears (both streaming deltas and
  // tool cards trigger it).
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "auto", block: "end" });
  }, [items]);

  return (
    <div style={{ flex: 1, overflowY: "auto", minHeight: 0, padding: "4px 2px" }}>
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
          <ToolCardView key={item.card.callId} card={item.card} onOpenRecord={onOpenRecord} />
        );
      })}
      {running && (
        <Text type="secondary" style={{ fontSize: 11, display: "block", margin: "2px 4px" }}>
          …
        </Text>
      )}
      <div ref={bottomRef} />
    </div>
  );
}
