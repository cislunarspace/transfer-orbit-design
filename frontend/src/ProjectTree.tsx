// 项目树组件：基于 Ant Design Tree 与 Dropdown 实现右键菜单、勾选多选（绘制所选）、
// 星标与备注编辑、删除确认与稳定性分析
// Project tree: an Ant Design Tree + Dropdown component with context menu, check-based multi-select
// (plot selected), star/note editing, delete confirmation, and stability analysis.

import { useState, type Key } from "react";
import { Tree, Dropdown, Modal, Typography, message, Button, Input, Tooltip } from "antd";
import type { MenuProps } from "antd";
import {
  RocketOutlined,
  LineChartOutlined,
  DeleteOutlined,
  EditOutlined,
  StarFilled,
  StarOutlined,
} from "@ant-design/icons";
import type { ArtifactSummary } from "./projectApi";
import { catalogDelete, catalogTag, catalogQuery, computeStability, STAR_TAG } from "./catalogApi";
import { useTranslation } from "./i18n";

const { Text } = Typography;

// 备注摘要截断长度（Tooltip 悬停显示）
// Truncation length for the note preview (shown in the hover Tooltip).
const NOTE_PREVIEW_LEN = 80;

const GROUP_LABELS: Record<string, { label: string; icon: string }> = {
  orbit: { label: "轨道", icon: "🪐" },
  family: { label: "轨道族", icon: "🌀" },
  transfer: { label: "转移", icon: "🚀" },
  ephemeris: { label: "星历", icon: "📡" },
};

export interface ProjectTreeProps {
  artifacts: ArtifactSummary[];
  selectedId: string | null;
  onSelect: (a: ArtifactSummary | null) => void;
  onRemove: (artifactId: string) => void;
  onOpenStationKeeping?: (a: ArtifactSummary) => void;
  onRefresh?: () => void;
  /** 勾选 ≥2 条后点“绘制所选”：回传勾选的叶子集合 */
  /** After checking ≥2 leaves, "Plot Selected" returns the checked leaf set. */
  onPlotSelected?: (items: ArtifactSummary[]) => void;
  /** 星标/备注保存成功后回传，供调用方同步树行数据 */
  /** Called back after a successful star/note save so the caller can sync the tree row. */
  onMetaChange?: (recordId: string, tags: string[], note?: string) => void;
}

export function ProjectTree({
  artifacts,
  selectedId,
  onSelect,
  onRemove,
  onOpenStationKeeping,
  onRefresh,
  onPlotSelected,
  onMetaChange,
}: ProjectTreeProps) {
  const { t } = useTranslation();
  const [stabilityResult, setStabilityResult] = useState<Record<string, unknown> | null>(null);
  const [stabilityModalOpen, setStabilityModalOpen] = useState(false);
  // 勾选多选（父子联动）：与单击选中互不干扰
  // Check-based multi-select (parent-child cascade): never interferes with single-click selection.
  const [checkedKeys, setCheckedKeys] = useState<Key[]>([]);
  // 编辑备注弹窗：目标行 + 草稿 + 保存时使用的当前 tags
  // Edit-note modal: target row, draft text, and the current tags used when saving.
  const [noteEditing, setNoteEditing] = useState<ArtifactSummary | null>(null);
  const [noteDraft, setNoteDraft] = useState("");
  const [noteTags, setNoteTags] = useState<string[] | null>(null);
  const [savingNote, setSavingNote] = useState(false);

  const checkedItems = artifacts.filter((a) => checkedKeys.includes(a.artifactId));

  const isStarred = (a: ArtifactSummary) => (a.tags ?? []).includes(STAR_TAG);

  // 行数据缺 tags（会话产物）时先查详情取当前 tags，再整表替换
  // When row data lacks tags (session artifacts), fetch the detail first, then replace wholesale.
  const currentTagsOf = async (a: ArtifactSummary): Promise<string[]> => {
    if (a.tags) return a.tags;
    if (!a.recordId) return [];
    const resp = await catalogQuery({ record_id: a.recordId });
    return (resp.records[0]?.tags as string[] | undefined) ?? [];
  };

  // 星标切换：tags 含 ★ 则移除、不含则加入（note 不传 = 保留原注释）
  // Star toggle: remove ★ if present, add it otherwise (omitting note keeps the existing note).
  const handleToggleStar = async (a: ArtifactSummary) => {
    if (!a.recordId) return;
    try {
      const tags = await currentTagsOf(a);
      const next = tags.includes(STAR_TAG) ? tags.filter((x) => x !== STAR_TAG) : [...tags, STAR_TAG];
      await catalogTag(a.recordId, next);
      onMetaChange?.(a.recordId, next);
    } catch (e) {
      message.error(`${t("tree.star_toggle")}: ${String(e)}`);
    }
  };

  const openNoteEditor = async (a: ArtifactSummary) => {
    setNoteEditing(a);
    setNoteDraft(a.note ?? "");
    try {
      setNoteTags(await currentTagsOf(a));
    } catch {
      setNoteTags([]);
    }
  };

  const handleSaveNote = async () => {
    if (!noteEditing?.recordId) return;
    setSavingNote(true);
    try {
      const tags = noteTags ?? [];
      await catalogTag(noteEditing.recordId, tags, noteDraft);
      onMetaChange?.(noteEditing.recordId, tags, noteDraft);
      message.success(t("tree.note_saved"));
      setNoteEditing(null);
    } catch (e) {
      message.error(`${t("tree.note_save_failed")}: ${String(e)}`);
    } finally {
      setSavingNote(false);
    }
  };

  const treeData = Object.entries(GROUP_LABELS).map(([typeKey, { label, icon }]) => {
    const items = artifacts.filter((a) => a.artifactType === typeKey);
    return {
      title: `${icon} ${label} (${items.length})`,
      key: `group_${typeKey}`,
      selectable: false,
      children: items.map((item) => ({
        title: item.label,
        key: item.artifactId,
        isLeaf: true,
        data: item,
      })),
    };
  });

  const handleRightClick = (item: ArtifactSummary): MenuProps["items"] => {
    const isOrbitOrFamily = item.artifactType === "orbit" || item.artifactType === "family";
    const hasEphemeris = item.artifactType === "ephemeris" || (item as any).hasEphemeris;

    return [
      {
        key: "station_keeping",
        icon: <RocketOutlined />,
        label: "轨道保持...",
        disabled: !hasEphemeris,
        onClick: () => onOpenStationKeeping?.(item),
      },
      {
        key: "stability",
        icon: <LineChartOutlined />,
        label: "查看轨道稳定性",
        disabled: !isOrbitOrFamily,
        onClick: async () => {
          try {
            const data = await computeStability(item.recordId || item.artifactId);
            setStabilityResult(data);
            setStabilityModalOpen(true);
          } catch (e) {
            message.error(`计算稳定性失败: ${String(e)}`);
          }
        },
      },
      {
        key: "edit_note",
        icon: <EditOutlined />,
        label: t("tree.edit_note"),
        disabled: !item.recordId,
        onClick: () => openNoteEditor(item),
      },
      {
        type: "divider",
      },
      {
        key: "delete",
        icon: <DeleteOutlined />,
        danger: true,
        label: "永久删除 (物理删除文件)",
        onClick: () => {
          Modal.confirm({
            title: "确认物理删除",
            content: `确定要从磁盘永久删除轨道记录 ${item.label} (ID: ${item.recordId || item.artifactId}) 吗？此操作不可恢复。`,
            okText: "删除",
            okType: "danger",
            cancelText: "取消",
            onOk: async () => {
              try {
                if (item.recordId) {
                  await catalogDelete([item.recordId]);
                }
                onRemove(item.artifactId);
                message.success("删除成功");
                onRefresh?.();
              } catch (e) {
                message.error(`删除失败: ${String(e)}`);
              }
            },
          });
        },
      },
    ];
  };

  return (
    <div style={{ fontSize: 12 }}>
      {/* 勾选 ≥2 条时出现“绘制所选”入口；单击单条仍立即绘制 */}
      {/* The "Plot Selected" entry appears once ≥2 leaves are checked; single-click still plots immediately. */}
      {checkedItems.length >= 2 && (
        <Button
          size="small"
          type="primary"
          style={{ marginBottom: 4 }}
          onClick={() => onPlotSelected?.(checkedItems)}
        >
          {t("tree.plot_selected")} ({checkedItems.length})
        </Button>
      )}
      <Tree
        showIcon={false}
        defaultExpandAll
        checkable
        selectedKeys={selectedId ? [selectedId] : []}
        checkedKeys={checkedKeys}
        onCheck={(checked: Key[] | { checked: Key[] }) => {
          setCheckedKeys(Array.isArray(checked) ? checked : checked.checked);
        }}
        treeData={treeData}
        onSelect={(keys, info: any) => {
          if (keys.length > 0 && info.node?.data) {
            onSelect(info.node.data as ArtifactSummary);
          } else {
            onSelect(null);
          }
        }}
        titleRender={(node: any) => {
          if (!node.data) {
            return <Text strong style={{ fontSize: 12 }}>{node.title}</Text>;
          }
          const item = node.data as ArtifactSummary;
          const starred = isStarred(item);
          const labelSpan = <span title={item.label}>{item.label}</span>;
          return (
            <Dropdown menu={{ items: handleRightClick(item) }} trigger={["contextMenu"]}>
              <div style={{ display: "inline-flex", alignItems: "center", width: "100%", gap: 2 }}>
                {/* 星标切换：点击不改选中，不冒泡触发树选中 */}
                {/* Star toggle: clicking neither selects nor bubbles into a tree selection. */}
                <span
                  role="button"
                  aria-label={t("tree.star_toggle")}
                  onClick={(e) => {
                    e.stopPropagation();
                    handleToggleStar(item);
                  }}
                  style={{
                    cursor: "pointer",
                    color: starred ? "#faad14" : "#bfbfbf",
                    fontSize: 11,
                    lineHeight: 1,
                    display: "inline-flex",
                  }}
                >
                  {starred ? <StarFilled /> : <StarOutlined />}
                </span>
                {item.note ? (
                  <Tooltip title={item.note.length > NOTE_PREVIEW_LEN ? `${item.note.slice(0, NOTE_PREVIEW_LEN)}…` : item.note}>
                    {labelSpan}
                  </Tooltip>
                ) : (
                  labelSpan
                )}
              </div>
            </Dropdown>
          );
        }}
      />

      {/* 编辑备注：保存走 catalog_tag 整体替换（tags 用查得的当前值） */}
      {/* Edit note: saving goes through catalog_tag wholesale (tags = the fetched current values). */}
      <Modal
        title={t("tree.edit_note")}
        open={!!noteEditing}
        onCancel={() => setNoteEditing(null)}
        onOk={handleSaveNote}
        confirmLoading={savingNote}
        okText={t("action.save")}
        cancelText={t("action.cancel")}
        width={450}
      >
        <Input.TextArea
          rows={4}
          value={noteDraft}
          placeholder={t("tree.note_placeholder")}
          onChange={(e) => setNoteDraft(e.target.value)}
        />
      </Modal>

      <Modal
        title="轨道稳定性分析结果"
        open={stabilityModalOpen}
        footer={null}
        onCancel={() => setStabilityModalOpen(false)}
        width={600}
      >
        {stabilityResult ? (
          <pre style={{ maxHeight: 400, overflow: "auto", fontSize: 12, background: "#1f1f1f", padding: 12, borderRadius: 2 }}>
            {JSON.stringify(stabilityResult, null, 2)}
          </pre>
        ) : (
          <Text>正在加载稳定性数据...</Text>
        )}
      </Modal>
    </div>
  );
}
