// 记录详情面板：展示谱系、断链标记、物理属性，支持教学标注 (catalog_tag) 与族成员提升 (catalog_promote)
// Record detail panel: shows lineage, broken-link markers, and physical properties; supports teaching annotations
// (catalog_tag) and family-member promotion (catalog_promote).

import { useState, useEffect } from "react";
import { Card, Descriptions, Tag, Input, Button, InputNumber, Space, Typography, message } from "antd";
import { EditOutlined, ArrowUpOutlined, RocketOutlined } from "@ant-design/icons";
import { type CatalogRecord, catalogTag, catalogPromote } from "./catalogApi";

const { Text } = Typography;

interface RecordDetailPanelProps {
  record: CatalogRecord | null;
  onRefresh?: () => void;
  onOpenStationKeeping?: (rec: CatalogRecord) => void;
}

export function RecordDetailPanel({ record, onRefresh, onOpenStationKeeping }: RecordDetailPanelProps) {
  if (!record) {
    return (
      <Card size="small" title="记录详情" style={{ marginTop: 8 }}>
        <Text type="secondary" style={{ fontSize: 12 }}>请在上方项目树或轨道库中选中一条记录查看详情。</Text>
      </Card>
    );
  }

  const [tagsInput, setTagsInput] = useState<string>((record.tags || []).join(", "));
  const [noteInput, setNoteInput] = useState<string>(record.note || "");
  const [promoteIdx, setPromoteIdx] = useState<number>(0);
  const [savingTag, setSavingTag] = useState<boolean>(false);
  const [promoting, setPromoting] = useState<boolean>(false);

  useEffect(() => {
    setTagsInput((record.tags || []).join(", "));
    setNoteInput(record.note || "");
    setPromoteIdx(0);
  }, [record.record_id]);

  const handleSaveAnnotation = async () => {
    setSavingTag(true);
    try {
      const tagList = tagsInput.split(",").map((s) => s.trim()).filter(Boolean);
      await catalogTag(record.record_id, tagList, noteInput);
      message.success("教学标注保存成功");
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
    <Card size="small" title="记录详情" style={{ marginTop: 8 }} bodyStyle={{ padding: "8px 12px" }}>
      <Descriptions size="small" column={1} bordered={false}>
        <Descriptions.Item label="ID">
          <Text copyable style={{ fontSize: 11 }}>{record.record_id}</Text>
        </Descriptions.Item>
        <Descriptions.Item label="轨道族">
          <Tag color="blue">{record.orbit_family || "未指定"}</Tag>
          {record.libration_point && <Tag color="cyan">L{record.libration_point}</Tag>}
        </Descriptions.Item>
        {record.jacobi !== undefined && (
          <Descriptions.Item label="Jacobi">{Number(record.jacobi).toFixed(4)}</Descriptions.Item>
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

      {/* 教学标注与标签 */}
      <div style={{ marginTop: 10, borderTop: "1px dashed #434343", paddingTop: 8 }}>
        <Text strong style={{ fontSize: 11 }}>教学标注 (Tags & Note)</Text>
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
  );
}
