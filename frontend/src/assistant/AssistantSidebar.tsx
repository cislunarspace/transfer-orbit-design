// 助手边栏（CONTEXT.md 术语：助手边栏）：右侧可折叠、可拖宽的人机交互
// 面板。负责：折叠/宽度持久化、未配置空态引导、会话恢复、live 事件折叠、
// 发送/清空。agent loop 本身在后端（ADR 0023 决策 1），这里只做显示与
// 交互转发。
// Assistant sidebar (CONTEXT.md term): the collapsible, drag-resizable
// human-interaction panel on the right. Handles: collapse/width persistence,
// the not-configured empty state, session restore, folding the live event
// stream, send/clear. The agent loop itself lives in the backend (ADR 0023
// decision 1); this only renders and forwards interaction.

import { useCallback, useEffect, useRef, useState } from "react";
import { Button, Input, Spin, Tooltip, Typography, message } from "antd";
import {
  ClearOutlined,
  DoubleRightOutlined,
  RobotOutlined,
  SendOutlined,
  SettingOutlined,
} from "@ant-design/icons";
import {
  assistantClearHistory,
  assistantGetState,
  assistantSend,
  onAssistantEvent,
  type SelectionContext,
} from "./api";
import { foldEvent, restoreItems, type ChatItem } from "./chatModel";
import { ChatView } from "./ChatView";
import { useTranslation } from "../i18n";

const { Text } = Typography;

const COLLAPSED_KEY = "tod-assistant-collapsed";
const WIDTH_KEY = "tod-assistant-width";
const DEFAULT_WIDTH = 340;
const MIN_WIDTH = 280;
const MAX_WIDTH = 620;

export function AssistantSidebar({
  lang,
  selection,
  onArtifactProduced,
  onOpenRecord,
  onOpenSettings,
}: {
  lang: string;
  selection: SelectionContext | null;
  /** A1 语义：AI 产物自动入项目树（tool_done 携带 record_id 时触发，App 内去重登记） */
  onArtifactProduced: (recordId: string, tool: string) => void;
  /** 工具卡片"查看产物"按钮：画布绘图（复用 getArtifact 通道） */
  onOpenRecord: (recordId: string, tool: string) => void;
  /** 打开设置弹窗（空态"去设置"按钮的落点） */
  onOpenSettings: () => void;
}) {
  const { t } = useTranslation();
  const [collapsed, setCollapsed] = useState<boolean>(
    () => localStorage.getItem(COLLAPSED_KEY) === "1",
  );
  const [width, setWidth] = useState<number>(() => {
    const raw = Number(localStorage.getItem(WIDTH_KEY));
    return raw >= MIN_WIDTH && raw <= MAX_WIDTH ? raw : DEFAULT_WIDTH;
  });
  const [configured, setConfigured] = useState<boolean | null>(null);
  const [items, setItems] = useState<ChatItem[]>([]);
  const [draft, setDraft] = useState("");
  const [running, setRunning] = useState(false);
  const dragRef = useRef<{ startX: number; startWidth: number } | null>(null);
  // 最新回调经 ref 持有：事件订阅只建一次，回调随渲染更新
  // Latest callback held via a ref: the event subscription is created once while
  // the callback stays current across renders.
  const producedRef = useRef(onArtifactProduced);
  producedRef.current = onArtifactProduced;

  // 初始载入：配置状态 + 持久化会话恢复
  // Initial load: config state plus restore of the persisted session.
  const loadState = useCallback(async () => {
    try {
      const info = await assistantGetState();
      setConfigured(info.configured);
      setItems(restoreItems(info.history));
    } catch {
      setConfigured(false);
    }
  }, []);

  useEffect(() => {
    loadState();
  }, [loadState]);

  // 订阅 agent loop 事件流（delta / tool_* / message_done / error）。
  // tool_done 携带 record_id 时触发 A1 自动登记入项目树。
  // Subscribe to the agent-loop event stream (delta / tool_* / message_done /
  // error). A tool_done carrying a record_id triggers the A1 auto-registration
  // into the project tree.
  useEffect(() => {
    // listen 是异步的：StrictMode 双挂载（挂载→清理→再挂载）下，清理先于
    // promise resolve 执行，若只靠 unlisten 变量，首挂载的监听器会泄漏——
    // 每个事件被处理两次（delta 逐字重复）。用 cancelled 标记：清理之后
    // 才 resolve 的监听器立即退订。
    // listen is async: under StrictMode double-mount (mount → cleanup → mount)
    // the cleanup runs before the promise resolves, so a bare unlisten variable
    // leaks the first mount's listener — every event is handled twice (deltas
    // duplicate character by character). Guard with a cancelled flag: a listener
    // resolving after cleanup unsubscribes immediately.
    let cancelled = false;
    let unlisten: (() => void) | undefined;
    onAssistantEvent((payload) => {
      setItems((prev) => foldEvent(prev, payload));
      if (payload.kind === "tool_done" && payload.ok && payload.summary?.recordId) {
        producedRef.current?.(payload.summary.recordId, payload.tool);
      }
    }).then((u) => {
      if (cancelled) {
        u();
        return;
      }
      unlisten = u;
    });
    return () => {
      cancelled = true;
      unlisten?.();
    };
  }, []);

  const toggleCollapsed = (next: boolean) => {
    setCollapsed(next);
    localStorage.setItem(COLLAPSED_KEY, next ? "1" : "0");
    // 展开时刷新一次配置态（可能在设置弹窗里刚保存过）
    // Refresh config state on expand (it may have just been saved in the settings modal).
    if (!next) loadState();
  };

  // 拖拽调宽：右边栏，宽度 = 视口宽 − 鼠标 x。松手才持久化。
  // Drag to resize: it's a right sidebar, so width = viewport width − mouse x.
  // Persisted only on release.
  const onDragStart = (e: React.MouseEvent) => {
    e.preventDefault();
    dragRef.current = { startX: e.clientX, startWidth: width };
    const onMove = (ev: MouseEvent) => {
      const start = dragRef.current;
      if (!start) return;
      const delta = start.startX - ev.clientX;
      const next = Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, start.startWidth + delta));
      setWidth(next);
    };
    const onUp = () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
      setWidth((w) => {
        localStorage.setItem(WIDTH_KEY, String(w));
        return w;
      });
      dragRef.current = null;
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  };

  const handleSend = async () => {
    const text = draft.trim();
    if (!text || running) return;
    setDraft("");
    setItems((prev) => [...prev, { kind: "user", text }]);
    setRunning(true);
    try {
      // 命令在整轮 agent loop 结束时返回；期间 delta/tool_* 经事件流入。
      // 运行期错误已由 error 事件气泡呈现，这里不再重复 toast。
      // The command returns when the whole agent loop finishes; meanwhile
      // delta/tool_* stream in via events. Runtime errors are already shown as
      // error-event bubbles, so no duplicate toast here.
      await assistantSend(text, lang, selection);
    } catch (e) {
      console.error("assistant send failed:", e);
    } finally {
      setRunning(false);
    }
  };

  const handleClear = async () => {
    try {
      await assistantClearHistory();
      setItems([]);
    } catch (e) {
      message.error(String(e));
    }
  };

  // 折叠态：右边缘一条常显入口按钮（含未配置小圆点提示）
  // Collapsed: an always-visible entry button on the right edge (with a dot
  // hint when not configured).
  if (collapsed) {
    return (
      <div
        style={{
          width: 36,
          borderLeft: "1px solid var(--tod-border, #e8e8e8)",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          paddingTop: 8,
          background: "var(--tod-panel-bg, transparent)",
        }}
      >
        <Tooltip title={t("assistant.title")} placement="left">
          <Button
            type="text"
            icon={<RobotOutlined />}
            onClick={() => toggleCollapsed(false)}
            style={{ position: "relative" }}
          >
            {configured === false && (
              <span
                style={{
                  position: "absolute",
                  top: 4,
                  right: 4,
                  width: 6,
                  height: 6,
                  borderRadius: "50%",
                  background: "#faad14",
                }}
              />
            )}
          </Button>
        </Tooltip>
      </div>
    );
  }

  return (
    <div
      style={{
        width,
        borderLeft: "1px solid var(--tod-border, #e8e8e8)",
        display: "flex",
        flexDirection: "column",
        background: "var(--tod-panel-bg, transparent)",
        position: "relative",
        flexShrink: 0,
      }}
    >
      {/* 左缘拖拽调宽手柄 */}
      <div
        onMouseDown={onDragStart}
        style={{
          position: "absolute",
          left: -3,
          top: 0,
          bottom: 0,
          width: 6,
          cursor: "col-resize",
          zIndex: 10,
        }}
      />

      {/* 头部：标题 + 清空 + 折叠 */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 4,
          padding: "6px 8px",
          borderBottom: "1px solid var(--tod-border, #e8e8e8)",
        }}
      >
        <RobotOutlined />
        <Text strong style={{ fontSize: 13, flex: 1 }}>
          {t("assistant.title")}
        </Text>
        <Tooltip title={t("assistant.clear")}>
          <Button type="text" size="small" icon={<ClearOutlined />} onClick={handleClear} />
        </Tooltip>
        <Tooltip title={t("assistant.collapse")}>
          <Button
            type="text"
            size="small"
            icon={<DoubleRightOutlined />}
            onClick={() => toggleCollapsed(true)}
          />
        </Tooltip>
      </div>

      {configured === null ? (
        // 配置状态加载中
        // Config state loading.
        <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <Spin size="small" />
        </div>
      ) : configured === false ? (
        // 空态引导：未配置模型服务（ADR 0022 决策 5 BYOK，Q8）
        // Empty-state guidance: model service not configured yet (ADR 0022
        // decision 5 BYOK, Q8).
        <div
          style={{
            flex: 1,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            gap: 12,
            padding: 24,
            textAlign: "center",
          }}
        >
          <RobotOutlined style={{ fontSize: 32, opacity: 0.4 }} />
          <Text type="secondary" style={{ fontSize: 12 }}>
            {t("assistant.empty_config")}
          </Text>
          <Button type="primary" icon={<SettingOutlined />} onClick={onOpenSettings}>
            {t("assistant.go_settings")}
          </Button>
        </div>
      ) : (
        <>
          <ChatView items={items} running={running} onOpenRecord={onOpenRecord} />
          {/* 输入区：运行中禁用（后端单并发门禁的对应 UI） */}
          <div
            style={{
              display: "flex",
              gap: 6,
              padding: 8,
              borderTop: "1px solid var(--tod-border, #e8e8e8)",
            }}
          >
            <Input.TextArea
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder={t("assistant.input_placeholder")}
              autoSize={{ minRows: 1, maxRows: 5 }}
              disabled={running}
              onPressEnter={(e) => {
                if (!e.shiftKey) {
                  e.preventDefault();
                  handleSend();
                }
              }}
            />
            <Button
              type="primary"
              icon={<SendOutlined />}
              loading={running}
              onClick={handleSend}
              disabled={!draft.trim()}
            />
          </div>
        </>
      )}
    </div>
  );
}
