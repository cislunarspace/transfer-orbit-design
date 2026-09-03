// 记录详情面板：展示谱系、断链标记、物理属性，支持备注与标签 (catalog_tag) 与族成员提升 (catalog_promote)
// Record detail panel: shows lineage, broken-link markers, and physical properties; supports notes & tags
// (catalog_tag) and family-member promotion (catalog_promote).

import { useState, useEffect } from "react";
import { Card, Descriptions, Tag, Input, Button, InputNumber, Space, Typography, message } from "antd";
import { EditOutlined, ArrowUpOutlined, RocketOutlined } from "@ant-design/icons";
import { type CatalogRecord, catalogTag, catalogPromote, STAR_TAG } from "./catalogApi";
import { useTranslation } from "./i18n";

const { Text } = Typography;

/** top-N 可行解候选的展示模型（#430）：App 从 transfer_design 响应映射，
 *  与画布层解耦——无轨迹降级的候选也在此列参数。 */
/** The display model of a top-N feasible-solution candidate (#430): App maps
 *  it from the transfer_design response, decoupled from the canvas layer —
 *  trackless degraded candidates still list their parameters here. */
export interface TransferCandidateView {
  key: string;
  /** Δv 升序名次（1 起） */
  rank: number;
  deltaVKmS: number;
  /** 已格式化的 TLI 历元（未携带为占位符） */
  tliEpochText: string;
  /** 已格式化的飞行时间（未携带为占位符） */
  tofSecText: string;
  selected: boolean;
  /** 打靶精化（True）或网格估计（False）口径 */
  refined: boolean;
  /** 是否携带轨迹快照（无轨迹的不上画布，仅列参数） */
  hasTrajectory: boolean;
}

interface RecordDetailPanelProps {
  record: CatalogRecord | null;
  /** 最近一次 top_n 转移搜索的候选集（含选中解；恰一候选时 App 不传） */
  /** The candidate set of the latest top_n transfer search (selected included;
   *  App omits it for a single-candidate run). */
  transferCandidates?: TransferCandidateView[];
  /** 树选中行的 label，标题联动回显（#468）；缺省保持原标题 */
  /** The selected tree row's label, echoed in the title (#468); the title
   *  stays plain when absent. */
  selectedLabel?: string | null;
  onRefresh?: () => void;
  onOpenStationKeeping?: (rec: CatalogRecord) => void;
}

export function RecordDetailPanel({ record, transferCandidates, selectedLabel, onRefresh, onOpenStationKeeping }: RecordDetailPanelProps) {
  const { t } = useTranslation();

  // hooks 规则（#437）：无论 record 是否为 null，每次渲染调用相同数量、
  // 相同顺序的 hooks；空态早返回必须在所有 hooks 之后。
  // Hooks rule (#437): the same hooks run in the same order regardless of
  // record being null; the empty-state early return must follow all hooks.
  const [tagsInput, setTagsInput] = useState<string>("");
  const [noteInput, setNoteInput] = useState<string>("");
  const [promoteIdx, setPromoteIdx] = useState<number>(0);
  const [savingTag, setSavingTag] = useState<boolean>(false);
  const [promoting, setPromoting] = useState<boolean>(false);

  useEffect(() => {
    if (!record) return;
    setTagsInput((record.tags || []).join(", "));
    setNoteInput(record.note || "");
    setPromoteIdx(0);
  }, [record?.record_id]);

  // 标题联动（#468）：带上树选中行的 label，空态与有记录态共用
  // Title linkage (#468): carries the selected tree row's label, shared by
  // both the empty and the populated states.
  const detailTitle = selectedLabel ? `记录详情 · ${selectedLabel}` : "记录详情";

  if (!record) {
    return (
      <>
        {transferCandidates && transferCandidates.length > 0 && (
          <CandidateComparisonCard candidates={transferCandidates} />
        )}
        <Card size="small" title={detailTitle} style={{ marginTop: 8 }}>
          <Text type="secondary" style={{ fontSize: 12 }}>请在上方项目树或轨道库中选中一条记录查看详情。</Text>
        </Card>
      </>
    );
  }

  const handleSaveAnnotation = async () => {
    setSavingTag(true);
    try {
      const raw = tagsInput.split(",").map((s) => s.trim()).filter(Boolean);
      // 星标 (★) 为保留值：编辑框输入的 ★ 剥离并提示，星标经项目树星形图标设置
      // The star (★) is reserved: ★ typed here is stripped with a hint; stars are set via the tree's star icon.
      const tagList = raw.filter((tag) => tag !== STAR_TAG);
      if (tagList.length !== raw.length) {
        message.info(t("panel.star_reserved"));
      }
      await catalogTag(record.record_id, tagList, noteInput);
      message.success(t("panel.annotation_saved"));
      onRefresh?.();
    } catch (e) {
      message.error(`保存失败: ${String(e)}`);
    } finally {
      setSavingTag(false);
    }
  };

  const handlePromote = async () => {
    setPromoting(true);
    try {
      const newRecId = await catalogPromote(record.record_id, promoteIdx);
      if (newRecId) {
        message.success(`成员 #${promoteIdx} 成功提升为独立记录: ${newRecId}`);
        onRefresh?.();
      }
    } catch (e) {
      message.error(`提升失败: ${String(e)}`);
    } finally {
      setPromoting(false);
    }
  };

  const isFamily = (record.member_count ?? 0) > 1 || record.source_tool === "orbit_family_generation";
  const hasEphemeris = record.has_ephemeris;

  return (
    <>
    {transferCandidates && transferCandidates.length > 0 && (
      <CandidateComparisonCard candidates={transferCandidates} />
    )}
    <Card size="small" title={detailTitle} style={{ marginTop: 8 }} bodyStyle={{ padding: "8px 12px" }}>
      <Descriptions size="small" column={1} bordered={false}>
        <Descriptions.Item label="ID">
          <Text copyable style={{ fontSize: 11 }}>{record.record_id}</Text>
        </Descriptions.Item>
        <Descriptions.Item label="轨道族">
          <Tag color="blue">{record.orbit_family || "未指定"}</Tag>
          {record.libration_point && <Tag color="cyan">L{record.libration_point}</Tag>}
        </Descriptions.Item>
        {/* jacobi 线上为包络数组 [min, max]：取下界渲染（与后端 record_to_artifact
            同口径），直接 Number(数组) 会得 NaN */}
        {record.jacobi !== undefined && (
          <Descriptions.Item label="Jacobi">
            {Number(Array.isArray(record.jacobi) ? record.jacobi[0] : record.jacobi).toFixed(4)}
          </Descriptions.Item>
        )}
        {record.member_count !== undefined && (
          <Descriptions.Item label="成员数">{record.member_count}</Descriptions.Item>
        )}
        <Descriptions.Item label="动力学段">
          <Space orientation="horizontal" size={4}>
            {record.has_cr3bp && <Tag color="green">CR3BP</Tag>}
            {record.has_ephemeris && <Tag color="purple">星历</Tag>}
          </Space>
        </Descriptions.Item>
        {record.source_record_id && (
          <Descriptions.Item label="上游谱系">
            <Text style={{ fontSize: 11 }}>{record.source_record_id}</Text>
          </Descriptions.Item>
        )}
      </Descriptions>

      {/* 轨道保持入口 */}
      <div style={{ marginTop: 8 }}>
        <Button
          size="small"
          type="primary"
          icon={<RocketOutlined />}
          disabled={!hasEphemeris}
          title={hasEphemeris ? "以此轨道星历为基准进行轨道保持控制评估" : "该记录无星历段，无法开展轨道保持"}
          style={{ width: "100%" }}
          onClick={() => onOpenStationKeeping?.(record)}
        >
          开展轨道保持...
        </Button>
      </div>

      {/* 族成员提升 */}
      {isFamily && (
        <div style={{ marginTop: 10, borderTop: "1px dashed #434343", paddingTop: 8 }}>
          <Text strong style={{ fontSize: 11 }}>族成员提升为独立记录</Text>
          <Space orientation="horizontal" style={{ width: "100%", marginTop: 4 }}>
            <InputNumber
              size="small"
              min={0}
              max={Math.max(0, (record.member_count ?? 1) - 1)}
              value={promoteIdx}
              onChange={(v) => setPromoteIdx(v || 0)}
              style={{ width: 80 }}
            />
            <Button
              size="small"
              icon={<ArrowUpOutlined />}
              loading={promoting}
              onClick={handlePromote}
            >
              提升
            </Button>
          </Space>
        </div>
      )}

      {/* 备注与标签（原“教学标注”，2026-08 更名） */}
      {/* Notes & tags (renamed from the former "teaching annotation" in 2026-08). */}
      <div style={{ marginTop: 10, borderTop: "1px dashed #434343", paddingTop: 8 }}>
        <Text strong style={{ fontSize: 11 }}>{t("panel.annotation_title")}</Text>
        <Input
          size="small"
          placeholder="标签 (逗号分隔)"
          value={tagsInput}
          onChange={(e) => setTagsInput(e.target.value)}
          style={{ marginTop: 4 }}
        />
        <Input.TextArea
          size="small"
          rows={2}
          placeholder="笔记说明..."
          value={noteInput}
          onChange={(e) => setNoteInput(e.target.value)}
          style={{ marginTop: 4, fontSize: 12 }}
        />
        <Button
          size="small"
          icon={<EditOutlined />}
          loading={savingTag}
          onClick={handleSaveAnnotation}
          style={{ marginTop: 6, width: "100%" }}
        >
          保存标注
        </Button>
      </div>
    </Card>
    </>
  );
}

/** 可行解对比卡片（#430）：并列各候选 Δv/TLI/TOF，选中解与 refined 口径
 *  自述（混合口径共存时逐候选标注），无轨迹降级候选仅列参数。 */
/** The feasible-solution comparison card (#430): candidate Δv/TLI/TOF side
 *  by side, each self-describing its selected mark and refined caliber (per
 *  candidate when mixed), trackless degraded ones listing parameters only. */
function CandidateComparisonCard({ candidates }: { candidates: TransferCandidateView[] }) {
  const { t } = useTranslation();
  return (
    <Card size="small" title={t("panel.candidates_title")} bodyStyle={{ padding: "4px 12px" }}>
      {candidates.map((c) => (
        <div
          key={c.key}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            fontSize: 11,
            padding: "3px 0",
            borderBottom: "1px dashed rgba(128,128,128,0.25)",
          }}
        >
          <Text strong style={{ fontSize: 11, minWidth: 18 }}>#{c.rank}</Text>
          <Text code style={{ fontSize: 11 }}>Δv {c.deltaVKmS.toFixed(3)}</Text>
          <Text style={{ fontSize: 11 }}>TLI {c.tliEpochText}</Text>
          <Text style={{ fontSize: 11 }}>TOF {c.tofSecText}</Text>
          {c.selected ? (
            <Tag color="gold" style={{ marginInlineEnd: 0 }}>{t("panel.cand_selected")}</Tag>
          ) : null}
          <Tag style={{ marginInlineEnd: 0 }}>
            {c.refined ? t("panel.cand_refined_true") : t("panel.cand_refined_false")}
          </Tag>
          {!c.hasTrajectory && (
            <Tag color="default" style={{ marginInlineEnd: 0 }}>{t("panel.cand_no_traj")}</Tag>
          )}
        </div>
      ))}
    </Card>
  );
}
