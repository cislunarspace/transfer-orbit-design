// 工具卡片：一次工具调用在对话流中的可视记录（CONTEXT.md 术语：工具卡片）。
// Tool card: the visible record of one tool call in the conversation flow.
// 状态机：proposed（待确认，可改参）→ running（不定态进度，ADR 0023 已知限制）
//        → done / error / rejected。

import { useEffect, useState } from "react";
import { Button, Modal, Typography, Input, Tag, Progress } from "antd";
import {
  CaretDownOutlined,
  CaretRightOutlined,
  CheckOutlined,
  CloseOutlined,
  EditOutlined,
  LoadingOutlined,
  RocketOutlined,
} from "@ant-design/icons";
import { assistantConfirmTool } from "./api";
import { useTranslation } from "../i18n";

const { Text } = Typography;

export interface ToolCardData {
  callId: string;
  tool: string;
  args: unknown;
  status: "proposed" | "running" | "done" | "error" | "rejected";
  /** tool_done 的摘要：status / recordId / scenarioFile / error.message */
  summary?: { status?: string; recordId?: string; scenarioFile?: string; error?: { message?: string } };
  /** 运行起始时间戳（ms），用于耗时显示 */
  startedAt?: number;
  /** 真进度分数 [0,1]（progressToken 通知；仅 live 运行中存在） */
  progress?: number;
  /** 进度可读消息（服务端下发的阶段说明） */
  progressMessage?: string;
}

export function ToolCardView({
  card,
  onOpenRecord,
  onApplyScenario,
}: {
  card: ToolCardData;
  onOpenRecord: (recordId: string, tool: string) => void;
  /** 应用情景（ADR 0027）：scenario_write 完成后的同语义跳转入口 */
  /** Apply scenario (ADR 0027): the same-semantics jump entry after a
   *  completed scenario_write. */
  onApplyScenario?: (path: string) => void;
}) {
  const { t } = useTranslation();
  const [editOpen, setEditOpen] = useState(false);
  const [editText, setEditText] = useState("");
  const [editError, setEditError] = useState("");
  const [elapsed, setElapsed] = useState(0);

  // 运行中每秒刷新耗时（无进度通知时是唯一的不定态指示；有真进度时
  // 进度条接管，耗时数字保留）
  // While running, refresh elapsed time every second (the only indeterminate
  // indicator before a progress notification arrives; kept alongside the bar).
  useEffect(() => {
    if (card.status !== "running") return;
    const base = card.startedAt ?? Date.now();
    const timer = setInterval(() => setElapsed(Math.round((Date.now() - base) / 1000)), 1000);
    return () => clearInterval(timer);
  }, [card.status, card.startedAt]);

  const argsText = JSON.stringify(card.args, null, 2);

  // 完成态折叠为单行摘要（工具名 + 状态 + record_id），点击展开参数与
  // 结果摘要（ADR 0026 决策 4）；待确认/运行中保持全文展示供审阅。
  const collapsible = card.status === "done" || card.status === "error" || card.status === "rejected";
  const [expanded, setExpanded] = useState(false);
  const showDetail = !collapsible || expanded;

  const statusTag = {
    proposed: <Tag color="gold">{t("assistant.card.proposed")}</Tag>,
    running: (
      <Tag icon={<LoadingOutlined />} color="processing">
        {t("assistant.card.running")} {elapsed}s
      </Tag>
    ),
    done: <Tag color="success">{t("assistant.card.done")}</Tag>,
    error: <Tag color="error">{t("assistant.card.failed")}</Tag>,
    rejected: <Tag>{t("assistant.card.rejected")}</Tag>,
  }[card.status];

  return (
    <div
      style={{
        border: "1px solid var(--tod-border, #d9d9d9)",
        borderRadius: 6,
        padding: "6px 8px",
        margin: "4px 0",
        fontSize: 12,
        background: "var(--tod-card-bg, rgba(128,128,128,0.06))",
      }}
    >
      <div
        style={{ display: "flex", alignItems: "center", gap: 6, cursor: collapsible ? "pointer" : undefined }}
        onClick={collapsible ? () => setExpanded((e) => !e) : undefined}
      >
        {collapsible ? (
          expanded ? <CaretDownOutlined /> : <CaretRightOutlined />
        ) : (
          <RocketOutlined />
        )}
        <Text code style={{ fontSize: 12 }}>{card.tool}</Text>
        {statusTag}
        {!showDetail && card.summary?.recordId && (
          <Text type="secondary" style={{ fontSize: 11, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {card.summary.recordId}
          </Text>
        )}
      </div>

      {/* 真进度（progressToken 通知，ADR 0023 限制已由 e2m2e 5.9.0 解除）：
          运行中且有进度时显示分数条与阶段消息；无进度保持耗时转圈不定态 */}
      {card.status === "running" && typeof card.progress === "number" && (
        <div style={{ marginTop: 6 }}>
          <Progress
            percent={Math.min(100, Math.max(0, Math.round(card.progress * 100)))}
            size="small"
            status="active"
          />
          {card.progressMessage && (
            <Text type="secondary" style={{ fontSize: 11 }}>
              {card.progressMessage}
            </Text>
          )}
        </div>
      )}

      {/* 参数摘要：确认前完整展示供审阅（ADR 0022 决策 4） */}
      {showDetail && (
        <pre
          style={{
            margin: "6px 0 0",
            padding: 6,
            fontSize: 11,
            maxHeight: 160,
            overflow: "auto",
            whiteSpace: "pre-wrap",
            wordBreak: "break-all",
            background: "var(--tod-code-bg, rgba(128,128,128,0.1))",
            borderRadius: 4,
          }}
        >
          {argsText}
        </pre>
      )}

      {card.status === "proposed" && (
        <div style={{ display: "flex", gap: 6, marginTop: 6 }}>
          <Button
            size="small"
            type="primary"
            icon={<CheckOutlined />}
            onClick={() => assistantConfirmTool(card.callId, true)}
          >
            {t("assistant.card.confirm")}
          </Button>
          <Button
            size="small"
            icon={<EditOutlined />}
            onClick={() => {
              setEditText(JSON.stringify(card.args, null, 2));
              setEditError("");
              setEditOpen(true);
            }}
          >
            {t("assistant.card.edit")}
          </Button>
          <Button
            size="small"
            danger
            icon={<CloseOutlined />}
            onClick={() => assistantConfirmTool(card.callId, false)}
          >
            {t("assistant.card.reject")}
          </Button>
        </div>
      )}

      {card.status === "done" && card.summary?.recordId && (
        <Button
          size="small"
          type="link"
          style={{ padding: 0, marginTop: 4 }}
          onClick={() => onOpenRecord(card.summary!.recordId!, card.tool)}
        >
          {t("assistant.card.view_artifact")}（{card.summary.recordId}）
        </Button>
      )}
      {card.status === "done" && card.tool === "scenario_write" && card.summary?.scenarioFile && (
        <Button
          size="small"
          type="link"
          style={{ padding: 0, marginTop: 4 }}
          onClick={() => onApplyScenario?.(card.summary!.scenarioFile!)}
        >
          {t("assistant.card.apply_scenario")}（{card.summary.scenarioFile.split(/[\\/]/).pop()}）
        </Button>
      )}
      {card.status === "error" && showDetail && card.summary?.error?.message && (
        <Text type="danger" style={{ fontSize: 11, display: "block", marginTop: 4 }}>
          {card.summary.error.message}
        </Text>
      )}

      {/* 改参弹窗：JSON 编辑，确认时带改后参数（ADR 0022 决策 4 可改参） */}
      <Modal
        title={t("assistant.card.edit_title")}
        open={editOpen}
        onCancel={() => setEditOpen(false)}
        onOk={() => {
          try {
            const parsed = JSON.parse(editText);
            setEditOpen(false);
            assistantConfirmTool(card.callId, true, parsed);
          } catch {
            setEditError(t("assistant.card.edit_bad_json"));
          }
        }}
        okText={t("assistant.card.confirm")}
        cancelText={t("assistant.card.cancel")}
      >
        <Input.TextArea
          rows={12}
          value={editText}
          onChange={(e) => setEditText(e.target.value)}
          style={{ fontFamily: "monospace", fontSize: 12 }}
        />
        {editError && <Text type="danger" style={{ fontSize: 12 }}>{editError}</Text>}
      </Modal>
    </div>
  );
}
