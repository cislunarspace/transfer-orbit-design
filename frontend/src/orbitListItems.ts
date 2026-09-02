// 画布轨道清单的数据装配（#469）：从 OrbitCanvas 拆出的纯函数，供左侧
// 边栏常驻清单与画布渲染共用同一取色/灰显口径。
// Orbit-list assembly (#469): pure functions split out of OrbitCanvas so the
// persistent sidebar list and the canvas render share one coloring/graying rule.

import * as THREE from "three";
import { jacobiColor, jacobiNorm } from "./jacobiColormap";
import type { DataFrameTag } from "./trajectoryParsing";
import type { FrameMode } from "./OrbitCanvas";

/** 清单行：色样（实际渲染色，灰显已套用）+ 标签 + 数据系标注 + 灰显标记。 */
/** One list row: swatch (the actual render color, graying applied), label,
 *  data-frame tag, and the grayed flag. */
export interface OrbitListItem {
  label: string;
  frame?: string;
  color: string;
  grayed: boolean;
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
