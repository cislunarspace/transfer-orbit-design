// 项目树：按 artifact_type 分组（分组标签对齐 PyQt 版 _TYPE_GROUP_LABELS）。

import { useEffect, useState } from "react";
import type { ArtifactSummary } from "./projectApi";

const GROUP_LABELS: Record<string, string> = {
  orbit: "🪐 轨道",
  family: "🌀 轨道族",
  transfer: "🚀 转移",
  ephemeris: "📡 星历",
};

export interface ProjectTreeProps {
  artifacts: ArtifactSummary[];
  onSelect: (a: ArtifactSummary | null) => void;
  onRemove: (artifactId: string) => void;
}

export function ProjectTree({ artifacts, onSelect, onRemove }: ProjectTreeProps) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set(Object.keys(GROUP_LABELS)));

  useEffect(() => {
    // 新类型出现时默认展开
    const types = new Set(artifacts.map((a) => a.artifactType));
    setExpanded((prev) => {
      const next = new Set(prev);
      for (const t of types) if (!prev.has(t)) next.add(t);
      return next;
    });
  }, [artifacts]);

  const grouped = Object.entries(GROUP_LABELS).map(([type, label]) => ({
    type,
    label,
    items: artifacts.filter((a) => a.artifactType === type),
  }));

  return (
    <div style={{ fontSize: 13 }}>
      {grouped.map(({ type, label, items }) => (
        <div key={type}>
          <div
            style={{ cursor: "pointer", padding: "4px 0", userSelect: "none" }}
            onClick={() =>
              setExpanded((prev) => {
                const next = new Set(prev);
                if (next.has(type)) next.delete(type);
                else next.add(type);
                return next;
              })
            }
          >
            {expanded.has(type) ? "▾" : "▸"} {label}（{items.length}）
          </div>
          {expanded.has(type) &&
            items.map((a) => (
              <div
                key={a.artifactId}
                style={{ display: "flex", alignItems: "center", padding: "2px 0 2px 20px" }}
              >
                <span
                  style={{ flex: 1, cursor: "pointer", overflow: "hidden", textOverflow: "ellipsis" }}
                  title={`${a.label} · ${a.recordId ?? ""}`}
                  onClick={() => onSelect(a)}
                >
                  {a.label}
                </span>
                <button
                  style={{ border: "none", background: "none", color: "#e57373", cursor: "pointer" }}
                  title="移除"
                  onClick={() => onRemove(a.artifactId)}
                >
                  ×
                </button>
              </div>
            ))}
        </div>
      ))}
    </div>
  );
}
