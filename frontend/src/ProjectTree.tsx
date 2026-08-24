// 项目树组件：基于 Ant Design Tree 与 Dropdown 实现右键菜单、多选、删除确认与稳定性分析

import { useState } from "react";
import { Tree, Dropdown, Modal, Typography, message } from "antd";
import type { MenuProps } from "antd";
import {
  RocketOutlined,
  LineChartOutlined,
  DeleteOutlined,
} from "@ant-design/icons";
import type { ArtifactSummary } from "./projectApi";
import { catalogDelete, computeStability } from "./catalogApi";

const { Text } = Typography;

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
}

export function ProjectTree({
  artifacts,
  selectedId,
  onSelect,
  onRemove,
  onOpenStationKeeping,
  onRefresh,
}: ProjectTreeProps) {
  const [stabilityResult, setStabilityResult] = useState<Record<string, unknown> | null>(null);
  const [stabilityModalOpen, setStabilityModalOpen] = useState(false);

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
      <Tree
        showIcon={false}
        defaultExpandAll
        selectedKeys={selectedId ? [selectedId] : []}
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
          return (
            <Dropdown menu={{ items: handleRightClick(item) }} trigger={["contextMenu"]}>
              <div style={{ display: "inline-block", width: "100%" }}>
                <span title={item.label}>{item.label}</span>
              </div>
            </Dropdown>
          );
        }}
      />

      <Modal
        title="轨道稳定性分析结果"
        open={stabilityModalOpen}
        footer={null}
        onCancel={() => setStabilityModalOpen(false)}
        width={600}
      >
        {stabilityResult ? (
          <pre style={{ maxHeight: 400, overflow: "auto", fontSize: 12, background: "#1f1f1f", padding: 12, borderRadius: 4 }}>
            {JSON.stringify(stabilityResult, null, 2)}
          </pre>
        ) : (
          <Text>正在加载稳定性数据...</Text>
        )}
      </Modal>
    </div>
  );
}
