// 画布轨道清单的数据装配（#469）：从 OrbitCanvas 拆出的纯函数，供左侧
// 边栏常驻清单与画布渲染共用同一取色/灰显口径。
// Orbit-list assembly (#469): pure functions split out of OrbitCanvas so the
// persistent sidebar list and the canvas render share one coloring/graying rule.

import * as THREE from "three";
import { jacobiColor, jacobiNorm } from "./jacobiColormap";
import type { DataFrameTag } from "./trajectoryParsing";
import type { FrameMode } from "./OrbitCanvas";

/** 清单行：色样（实际渲染色，灰显已套用）+ 标签 + 数据系标注 + 灰显标记。
 *  trajIndex 回指 TrajectoryData 行号——清单过滤无标签行后行序与数据
 *  不再对齐，聚焦/预览/详情全部以 trajIndex 为准（#476，与画布拾取
 *  同一索引空间）。 */
/** One list row: swatch (the actual render color, graying applied), label,
 *  data-frame tag, and the grayed flag. trajIndex points back at the
 *  TrajectoryData row — after unlabeled rows are filtered out, list order
 *  no longer matches data order, so focus/preview/details all key on
 *  trajIndex (#476, the same index space canvas picking uses). */
export interface OrbitListItem {
  label: string;
  frame?: string;
  color: string;
  grayed: boolean;
  trajIndex: number;
}

/** 惯性视图灰显判定（#428）：会合系数据系产物且无惯性段的轨迹灰显。
 *  OrbitCanvas 绘制/颜色条与轨道清单共用同一判定，防口径漂移（#469）。 */
/** Inertial-view graying test (#428): synodic data-frame products without an
 *  inertial segment gray out. Shared by the canvas draw, the colorbar, and
 *  the orbit list so the rule cannot drift between sites (#469). */
export function grayedFlags(args: {
  count: number;
  frame?: FrameMode;
  dataFrames?: DataFrameTag[];
  inertialGeometries?: (number[][] | null)[];
}): boolean[] {
  const inertial = args.frame === "inertial";
  return Array.from(
    { length: args.count },
    (_, i) =>
      inertial &&
      (args.dataFrames?.[i] ?? "synodic_nd") !== "inertial_km" &&
      !args.inertialGeometries?.[i],
  );
}

/** 装配清单行：有值轨迹按 Jacobi 归一化 coolwarm，无值回退色环；惯性视图
 *  下会合系产物灰显（与 OrbitCanvas 绘制同一判定，#428）。无标签项不进
 *  清单（与原画布图例同口径）。 */
/** Assemble list rows: coolwarm-normalized colors for Jacobi-valued
 *  trajectories, color-cycle fallback for the rest; synodic products gray out
 *  in the inertial view (the same test the canvas draw uses, #428). Unlabeled
 *  entries stay out of the list (same rule as the old in-canvas legend). */
export function buildOrbitListItems(args: {
  count: number;
  labels?: string[];
  frameLabels?: (string | undefined)[];
  jacobi?: (number | undefined)[];
  colorCycle: string[];
  frame?: FrameMode;
  dataFrames?: DataFrameTag[];
  inertialGeometries?: (number[][] | null)[];
}): OrbitListItem[] {
  const grayed = grayedFlags(args);
  const colors = trajectoryColorsHex(args.count, args.jacobi, args.colorCycle).colors;
  return (args.labels ?? [])
    .map((label, i) => ({
      label,
      frame: args.frameLabels?.[i],
      color: grayed[i] ? desaturateHex(colors[i]) : colors[i],
      grayed: grayed[i],
      trajIndex: i,
    }))
    .filter((item) => !!item.label);
}

/** 每条轨迹的实际渲染色（hex）：有 Jacobi 值按归一化 coolwarm，无值回退
 *  色环循环（#435）。range 是颜色条所需的实际 min/max（全无值时为 null）。
 *  渲染 effect 与左侧轨道清单共用，保证清单色样如实反映线上颜色（#469）。 */
/** The actual render color per trajectory (hex): normalized coolwarm for
 *  Jacobi-valued ones, color cycle fallback for the rest (#435). range carries
 *  the real min/max for the colorbar (null when no trajectory has a value).
 *  Shared by the render effect and the sidebar orbit list so list swatches mirror the lines (#469). */
export function trajectoryColorsHex(
  count: number,
  jacobi: (number | undefined)[] | undefined,
  cycle: string[],
): { colors: string[]; range: { jmin: number; jmax: number } | null } {
  const [jmin, jmax, jrange] = jacobiNorm(jacobi ?? []);
  const hasValue = (jacobi ?? []).some((v) => v !== undefined);
  const colors = Array.from({ length: count }, (_, i) => {
    const j = jacobi?.[i];
    return j !== undefined ? jacobiColor(j, jmin, jrange) : cycle[i % cycle.length];
  });
  return { colors, range: hasValue ? { jmin, jmax } : null };
}

/** 灰显色（#359 先例：惯性视图下会合系几何不可画）：保留 18% 饱和度
 *  让用户仍能分辨原色相归属，亮度不变；与轨道清单 swatch 共用同一函数，
 *  保证色样如实反映线上颜色。 */
/** The graying color (#359 precedent: synodic geometry is not drawable in
 *  the inertial view): keeps 18% saturation so the original hue stays
 *  identifiable, brightness unchanged; shared with the orbit-list swatch so the
 *  swatch mirrors the line color. */
export function desaturateHex(hex: string): string {
  const c = new THREE.Color(hex);
  const hsl = { h: 0, s: 0, l: 0 };
  c.getHSL(hsl);
  c.setHSL(hsl.h, hsl.s * 0.18, hsl.l);
  return `#${c.getHexString()}`;
}

/* ------------------------------------------------------------------ */
/* 轨道详情装配（#476）：点击清单项 → 中栏「轨道信息」页签展示。数据全部
 * 来自行对齐的 canvasData 数组 + 画布装配时记下的来源标注，不发后端请求。 */
/* Orbit-details assembly (#476): clicking a list row shows the orbit in the
 * mid pane's "orbit info" tab. All data comes from the row-aligned canvasData
 * arrays plus the source tags recorded during canvas assembly — no backend
 * calls. */

/** 轨迹来源（画布装配时逐层记下，行对齐）：固定层库记录 / 转移候选弧 /
 *  本次运行产物。id 与 label 供详情页展示（固定层 = 库记录 id）。 */
/** Per-row trajectory provenance recorded during canvas assembly: a pinned
 *  catalog record / a transfer candidate arc / the latest run product. id and
 *  label feed the details view (pinned → the catalog record id). */
export interface OrbitSource {
  layer: "pinned" | "candidate" | "result";
  id: string;
  label: string;
}

/** 轨道信息页签的展示模型：字段值均已本地化/格式化，面板只管渲染。 */
/** The orbit-info tab's display model: every field arrives localized and
 *  formatted, the panel only renders. */
export interface OrbitInfoView {
  label: string;
  /** 产物类型（段角色）：cr3bp 参考段 / 星历段；无段语义时缺省 */
  kind?: string;
  /** 数据系标签（本地化，与清单行标注同一句） */
  frame?: string;
  jacobi?: number;
  points: number;
  /** 时间跨度（已格式化）；无时刻轨迹缺省 */
  timeSpan?: string;
  source: string;
}

/** 时间跨度格式化（秒 → 紧凑读数）：<2 min 按秒，<2 d 按小时，其余按天。 */
/** Time-span formatting (seconds → compact readout): seconds under 2 min,
 *  hours under 2 d, days beyond. */
export function formatTimeSpan(seconds: number): string {
  if (seconds < 120) return `${Math.round(seconds)} s`;
  if (seconds < 172800) return `${(seconds / 3600).toFixed(1)} h`;
  return `${(seconds / 86400).toFixed(1)} d`;
}

/** 装配一条轨迹的详情：item 来自清单（携 trajIndex/标签/数据系标注），
 *  data 是 canvasData 在 trajIndex 处的行切片，source 来自画布装配的
 *  来源标注（行对齐）。 */
/** Assemble one trajectory's details: item comes from the list (carrying
 *  trajIndex/label/frame tag), data is the canvasData row slice at trajIndex,
 *  source is the row-aligned provenance from canvas assembly. */
export function buildOrbitInfo(args: {
  item: Pick<OrbitListItem, "label" | "frame">;
  data: {
    points: number;
    times: number[];
    jacobi?: number;
    role?: "cr3bp" | "ephemeris";
  };
  source?: OrbitSource;
  t: (key: string) => string;
}): OrbitInfoView {
  const { item, data, source, t } = args;
  const span =
    data.times.length >= 2
      ? formatTimeSpan(Math.abs(data.times[data.times.length - 1] - data.times[0]))
      : undefined;
  return {
    label: item.label,
    kind: data.role
      ? t(data.role === "cr3bp" ? "canvas.cr3bp_reference" : "canvas.design_ephemeris")
      : undefined,
    frame: item.frame,
    jacobi: data.jacobi,
    points: data.points,
    timeSpan: span,
    source: !source
      ? t("orbit_info.source.result")
      : source.layer === "pinned"
        ? `${t("orbit_info.source.pinned")} ${source.id}`
        : source.layer === "candidate"
          ? `${t("orbit_info.source.candidate")} ${source.label || source.id}`
          : t("orbit_info.source.result"),
  };
}
