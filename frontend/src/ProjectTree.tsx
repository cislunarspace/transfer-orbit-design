// 项目树组件：基于 Ant Design Tree 与 Dropdown 实现右键菜单、勾选多选（绘制所选）、
// 星标与备注编辑、删除确认；分组头为文字+计数徽标，叶子挂结构化摘要第二行，
// 容器量高后启用虚拟滚动（#468）
// Project tree: an Ant Design Tree + Dropdown component with context menu, check-based
// multi-select (plot selected), star/note editing, and delete confirmation; group headers
// are text + count badges, leaves carry a structured-summary second line, and the tree
// virtualizes once its container is measured (#468).

import { useEffect, useRef, useState, type Key } from "react";
import { Tree, Dropdown, Modal, Typography, message, Button, Input, Tooltip, Badge } from "antd";
import type { MenuProps } from "antd";
import {
  RocketOutlined,
  DeleteOutlined,
  EditOutlined,
  StarFilled,
  StarOutlined,
  PushpinFilled,
  PushpinOutlined,
} from "@ant-design/icons";
import type { ArtifactSummary } from "./projectApi";
import { catalogDelete, catalogTag, catalogQuery, STAR_TAG } from "./catalogApi";
import { useTranslation } from "./i18n";

const { Text } = Typography;

// 备注摘要截断长度（Tooltip 悬停显示）
// Truncation length for the note preview (shown in the hover Tooltip).
const NOTE_PREVIEW_LEN = 80;

// 分组文案（ADR 0020：严肃视觉，不用 emoji；计数走徽标）
// Group labels (ADR 0020: serious visuals, no emoji; counts go to badges).
const GROUP_LABELS: Record<string, string> = {
  orbit: "轨道",
  family: "轨道族",
  transfer: "转移",
  ephemeris: "星历",
};

// 受控展开初值：四个分组全部展开（去掉 defaultExpandAll，#468）
// Controlled-expansion initial value: all four groups expanded (defaultExpandAll removed, #468).
const GROUP_KEYS: Key[] = Object.keys(GROUP_LABELS).map((k) => `group_${k}`);

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
  /** 已钉住（固定层）记录的 recordId 集合，行内图钉高亮 */
  /** recordIds currently pinned to the canvas's pinned layer; highlights the row pushpin. */
  pinnedRecordIds?: string[];
  /** 图钉切换：钉住 = 固定层持续显示；取消 = 移出固定层 */
  /** Pushpin toggle: pinning keeps the record on the pinned layer; unpinning removes it. */
  onTogglePin?: (a: ArtifactSummary) => void;
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
  pinnedRecordIds,
  onTogglePin,
}: ProjectTreeProps) {
  const { t } = useTranslation();
  // 勾选多选（父子联动）：与单击选中互不干扰
  // Check-based multi-select (parent-child cascade): never interferes with single-click selection.
  const [checkedKeys, setCheckedKeys] = useState<Key[]>([]);
  // 受控展开（#468）：初始全展开，用户折叠后跨查询/刷新保持
  // Controlled expansion (#468): all expanded initially; user collapses persist across queries/refreshes.
  const [expandedKeys, setExpandedKeys] = useState<Key[]>(GROUP_KEYS);
  // 编辑备注弹窗：目标行 + 草稿 + 保存时使用的当前 tags
  // Edit-note modal: target row, draft text, and the current tags used when saving.
  const [noteEditing, setNoteEditing] = useState<ArtifactSummary | null>(null);
  const [noteDraft, setNoteDraft] = useState("");
  const [noteTags, setNoteTags] = useState<string[] | null>(null);
  const [savingNote, setSavingNote] = useState(false);

  // 容器量高（#468）：量得非零高度后传给 Tree 启用虚拟滚动；量不到
  // （jsdom 等环境）不传 height，回退全量渲染，行为不劣化
  // Container measuring (#468): a measured non-zero height enables the Tree's
  // virtual scroll; without one (jsdom etc.) height stays unset, falling back
  // to full rendering — no behavior regression.
  const treeWrapRef = useRef<HTMLDivElement>(null);
  const [treeHeight, setTreeHeight] = useState(0);
  useEffect(() => {
    const el = treeWrapRef.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const measure = () => setTreeHeight(el.clientHeight);
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    measure();
    return () => ro.disconnect();
  }, []);

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

  const treeData = Object.entries(GROUP_LABELS).map(([typeKey, label]) => {
    const items = artifacts.filter((a) => a.artifactType === typeKey);
    return {
      title: label,
      key: `group_${typeKey}`,
      count: items.length,
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
    const hasEphemeris = item.artifactType === "ephemeris" || item.hasEphemeris === true;

    return [
      {
        key: "station_keeping",
        icon: <RocketOutlined />,
        label: "轨道保持...",
        disabled: !hasEphemeris,
        onClick: () => onOpenStationKeeping?.(item),
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
    <div style={{ fontSize: 12, flex: 1, minHeight: 0, display: "flex", flexDirection: "column" }}>
      {/* 勾选 ≥2 条时出现“绘制所选”入口；单击单条仍立即绘制 */}
      {/* The "Plot Selected" entry appears once ≥2 leaves are checked; single-click still plots immediately. */}
      {checkedItems.length >= 2 && (
        <Button
          size="small"
          type="primary"
          style={{ marginBottom: 4, flexShrink: 0 }}
          onClick={() => onPlotSelected?.(checkedItems)}
        >
          {t("tree.plot_selected")} ({checkedItems.length})
        </Button>
      )}
      <div ref={treeWrapRef} style={{ flex: 1, minHeight: 0 }}>
        <Tree
          showIcon={false}
          height={treeHeight > 0 ? treeHeight : undefined}
          expandedKeys={expandedKeys}
          onExpand={(keys: Key[]) => setExpandedKeys(keys)}
          // ADR 0020 去动画：收起/展开过渡停用，子行直接显隐
          // ADR 0020 de-animation: the expand/collapse transition is off; child rows show and hide outright.
          motion={false}
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
              // 分组头（#468）：文字 + 计数徽标；空组整头置灰（组固定渲染，徽标同灰）
              // Group header (#468): text + count badge; an empty group greys out
              // (groups always render, so does the badge).
              const empty = node.count === 0;
              return (
                <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                  <Text strong style={{ fontSize: 12, color: empty ? "#8c8c8c" : undefined }}>
                    {node.title}
                  </Text>
                  <Badge
                    count={node.count}
                    showZero
                    overflowCount={99999}
                    style={{ backgroundColor: empty ? "#8c8c8c" : "#0958d9" }}
                  />
                </span>
              );
            }
            const item = node.data as ArtifactSummary;
            const starred = isStarred(item);
            const pinned = !!item.recordId && (pinnedRecordIds ?? []).includes(item.recordId);
            // 第二行结构化摘要（#468）：成员数 / L 点 / Jacobi，缺字段的部分不拼；
            // 全缺（会话产物行）不渲染第二行
            // Second-line structured summary (#468): member count / L point /
            // Jacobi; absent fields drop out, and a row with none (session
            // artifacts) renders no second line.
            const summaryParts: string[] = [];
            if ((item.memberCount ?? 0) > 1) summaryParts.push(`${item.memberCount} 成员`);
            if (item.librationPoint) summaryParts.push(`L${item.librationPoint}`);
            if (item.jacobi !== undefined && item.jacobi !== null) {
              summaryParts.push(`C ${Number(item.jacobi).toFixed(3)}`);
            }
            const labelSpan = (
              <span
                title={item.label}
                style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}
              >
                {item.label}
              </span>
            );
            return (
              <Dropdown menu={{ items: handleRightClick(item) }} trigger={["contextMenu"]}>
                <div
                  style={{
                    display: "flex",
                    alignItems: "flex-start",
                    width: "100%",
                    gap: 2,
                    minWidth: 0,
                  }}
                >
                  {/* 图钉切换：钉住/取消固定层，点击不改选中，不冒泡触发树选中 */}
                  {/* Pushpin toggle: pin/unpin the fixed layer; clicking neither selects nor bubbles. */}
                  <span
                    role="button"
                    aria-label={t("tree.pin_toggle")}
                    onClick={(e) => {
                      e.stopPropagation();
                      onTogglePin?.(item);
                    }}
                    style={{
                      cursor: "pointer",
                      color: pinned ? "#0958d9" : "#bfbfbf",
                      fontSize: 11,
                      lineHeight: 1,
                      display: "inline-flex",
                      flexShrink: 0,
                    }}
                  >
                    {pinned ? <PushpinFilled /> : <PushpinOutlined />}
                  </span>
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
                      flexShrink: 0,
                    }}
                  >
                    {starred ? <StarFilled /> : <StarOutlined />}
                  </span>
                  <div style={{ display: "flex", flexDirection: "column", minWidth: 0, flex: 1 }}>
                    {item.note ? (
                      <Tooltip title={item.note.length > NOTE_PREVIEW_LEN ? `${item.note.slice(0, NOTE_PREVIEW_LEN)}…` : item.note}>
                        {labelSpan}
                      </Tooltip>
                    ) : (
                      labelSpan
                    )}
                    {summaryParts.length > 0 && (
                      <span
                        style={{
                          fontSize: 10,
                          color: "#8c8c8c",
                          lineHeight: 1.4,
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {summaryParts.join(" · ")}
                      </span>
                    )}
                  </div>
                </div>
              </Dropdown>
            );
          }}
        />
      </div>

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
    </div>
  );
}
