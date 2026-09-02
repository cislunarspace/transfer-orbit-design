// 画布轨道清单（#469）：常驻左侧边栏，替代画布内图注——逐条列出当前画布
// 上的轨道（颜色样 + 名称 + 数据系标注），交互与原图例联动拾取（#460）
// 同口径：悬停预览、点击聚焦。聚焦/预览态由 App 持有，画布拾取与清单
// 交互双向一致。
// Canvas orbit list (#469): persistent in the left sidebar, replacing the
// in-canvas legend — one row per orbit on the canvas (swatch + name +
// data-frame tag), with the old legend-pick interactions (#460): hover
// previews, click focuses. Focus/preview state lives in App, so canvas
// picking and list interactions stay consistent both ways.

import { Typography } from "antd";
import { useTranslation } from "./i18n";
import type { OrbitListItem } from "./orbitListItems";

const { Text } = Typography;

export interface CanvasOrbitListProps {
  items: OrbitListItem[];
  /** 当前聚焦项（画布拾取或清单点击设置）；null = 无聚焦 */
  /** The focused item (set by canvas picking or a list click); null = none. */
  focusIndex: number | null;
  /** 惯性视图灰显项的注记（已本地化整句，如"会合系几何，惯性视图下不可画"） */
  /** The note for grayed items in the inertial view (a pre-localized sentence). */
  unavailableNote?: string;
  onFocusChange: (i: number | null) => void;
  onPreviewChange: (i: number | null) => void;
}

export function CanvasOrbitList({
  items,
  focusIndex,
  unavailableNote,
  onFocusChange,
  onPreviewChange,
}: CanvasOrbitListProps) {
  const { t } = useTranslation();
  if (items.length === 0) return null;
  return (
    <div data-testid="canvas-orbit-list" style={{ padding: "4px 8px" }}>
      <Text type="secondary" style={{ fontSize: 11 }}>
        {t("canvas.orbit_list")}
      </Text>
      <div style={{ display: "flex", flexDirection: "column", gap: 2, marginTop: 2 }}>
        {items.map((item, i) => (
          <div
            key={`${item.label}-${i}`}
            data-orbit-item=""
            data-focused={i === focusIndex ? "true" : "false"}
            onMouseEnter={() => onPreviewChange(i)}
            onMouseLeave={() => onPreviewChange(null)}
            onClick={() => onFocusChange(i === focusIndex ? null : i)}
            style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, cursor: "pointer" }}
          >
            <span
              data-testid="orbit-swatch"
              style={{
                width: 14,
                height: 2,
                background: item.color,
                display: "inline-block",
                // 聚焦标记（#460）：色样 1px 描边（ADR 0020 平面化）
                // Focus marker (#460): a 1px outline on the swatch (flat style per ADR 0020).
                ...(i === focusIndex ? { outline: "1px solid currentColor" } : {}),
              }}
            />
            <Text style={{ fontSize: 12 }}>{item.label}</Text>
            {item.frame && (
              <Text type="secondary" style={{ fontSize: 10, border: "1px solid rgba(128,128,128,0.4)", borderRadius: 3, padding: "0 3px" }}>
                {item.frame}
              </Text>
            )}
            {item.grayed && unavailableNote && (
              <Text data-testid="orbit-unavailable" type="secondary" style={{ fontSize: 10 }}>
                {unavailableNote}
              </Text>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
