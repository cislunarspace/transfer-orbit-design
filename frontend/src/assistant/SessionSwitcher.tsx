// 会话切换器（CONTEXT.md 术语）：助手边栏头部的会话管理控件。下拉按最近
// 活动倒序列出会话 + 新建按钮；重命名/删除收在下拉项悬浮操作中；删除需
// 二次确认，确认文案说明删会话不删轨道库记录（ADR 0025 决策 2/4）。
// 有进行中回复或未决确认时整体禁用并提示等待完成（ADR 0025 决策 5）。
// Session switcher (CONTEXT.md term): the session-management control at the
// assistant sidebar header. Dropdown lists sessions by recent activity with a
// new-session button; rename/delete live in per-item hover actions; delete
// asks for confirmation and clarifies that catalog records are kept
// (ADR 0025 decisions 2/4). Fully disabled with a wait hint while a reply is
// running or a confirmation is pending (ADR 0025 decision 5).

import { useState } from "react";
import { Button, Input, Modal, Select, Tooltip } from "antd";
import { DeleteOutlined, EditOutlined, PlusOutlined } from "@ant-design/icons";
import type { SessionMeta } from "./api";
import { useTranslation } from "../i18n";

export function SessionSwitcher({
  sessions,
  currentId,
  disabled,
  onSwitch,
  onNew,
  onRename,
  onDelete,
}: {
  sessions: SessionMeta[];
  currentId: string;
  /** 有进行中回复或未决确认（切换门禁的前端对应） */
  disabled: boolean;
  onSwitch: (id: string) => void;
  onNew: () => void;
  onRename: (id: string, title: string) => void;
  onDelete: (id: string) => void;
}) {
  const { t } = useTranslation();
  const [renameTarget, setRenameTarget] = useState<SessionMeta | null>(null);
  const [renameText, setRenameText] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<SessionMeta | null>(null);

  // 首次使用（index 为空）时下拉也要能显示当前会话本体
  const options = sessions.some((s) => s.id === currentId)
    ? sessions
    : [
        {
          id: currentId,
          title: "",
          createdAt: 0,
          updatedAt: 0,
          messageCount: 0,
          thinkingLevel: "",
        },
        ...sessions,
      ];

  const label = (s: SessionMeta) => s.title || t("assistant.session.untitled");

  return (
    <div style={{ display: "flex", flex: 1, gap: 4, minWidth: 0 }}>
      <Tooltip title={disabled ? t("assistant.session.switch_busy") : ""}>
        <div style={{ display: "flex", flex: 1, gap: 4, minWidth: 0 }}>
          <Select
            size="small"
            style={{ flex: 1, minWidth: 0 }}
            value={currentId}
            disabled={disabled}
            onChange={onSwitch}
            popupMatchSelectWidth={false}
            options={options.map((s) => ({ value: s.id, label: label(s) }))}
            optionRender={(option) => {
              const meta = options.find((s) => s.id === option.value);
              if (!meta) return option.label;
              return (
                <div style={{ display: "flex", alignItems: "center", gap: 2 }}>
                  <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis" }}>
                    {option.label}
                  </span>
                  <Button
                    size="small"
                    type="text"
                    icon={<EditOutlined />}
                    onClick={(e) => {
                      e.stopPropagation();
                      setRenameTarget(meta);
                      setRenameText(meta.title);
                    }}
                  />
                  <Button
                    size="small"
                    type="text"
                    danger
                    icon={<DeleteOutlined />}
                    onClick={(e) => {
                      e.stopPropagation();
                      setDeleteTarget(meta);
                    }}
                  />
                </div>
              );
            }}
          />
          <Button
            size="small"
            icon={<PlusOutlined />}
            disabled={disabled}
            onClick={onNew}
            title={t("assistant.session.new")}
          />
        </div>
      </Tooltip>

      <Modal
        title={t("assistant.session.rename_title")}
        open={!!renameTarget}
        onCancel={() => setRenameTarget(null)}
        onOk={() => {
          if (renameTarget) onRename(renameTarget.id, renameText);
          setRenameTarget(null);
        }}
        okText={t("assistant.session.rename")}
        cancelText={t("assistant.card.cancel")}
      >
        <Input
          value={renameText}
          onChange={(e) => setRenameText(e.target.value)}
          maxLength={60}
        />
      </Modal>

      <Modal
        title={t("assistant.session.delete_title")}
        open={!!deleteTarget}
        onCancel={() => setDeleteTarget(null)}
        onOk={() => {
          if (deleteTarget) onDelete(deleteTarget.id);
          setDeleteTarget(null);
        }}
        okText={t("assistant.session.delete")}
        okButtonProps={{ danger: true }}
        cancelText={t("assistant.card.cancel")}
      >
        {deleteTarget && (
          <>
            <div>{label(deleteTarget)}</div>
            <div style={{ marginTop: 8, fontSize: 12, color: "var(--tod-text-secondary, #8c8c8c)" }}>
              {t("assistant.session.delete_confirm")}
            </div>
          </>
        )}
      </Modal>
    </div>
  );
}
