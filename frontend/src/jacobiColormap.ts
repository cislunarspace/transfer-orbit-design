// Jacobi 常数着色：coolwarm 采样表 + 归一化（#435）。
//
// 画布硬编码 coolwarm colormap 的 9 档采样表线性插值（低 Jacobi 蓝端、
// 高 Jacobi 红端），不引入运行时依赖。原与 matplotlib 出图侧（已删的
// FamilyPlotter，#435 定的视觉语义）对齐；该侧随 #415 删除，此处保留
// 同一色板。
// 归一化口径照抄 matplotlib _get_jacobi_norm：全相等或仅一条时
// jrange 取 1.0 防除零，归一化值恒为 0 → 固定蓝端色。
// Jacobi-constant coloring: the coolwarm sample table plus normalization (#435).
//
// The canvas hardcodes a 9-stop sample of the coolwarm colormap with linear
// interpolation (low Jacobi blue, high Jacobi red), adding no runtime
// dependency. It originally matched the former matplotlib plot path (the
// FamilyPlotter side whose visual semantics #435 fixed); that side was removed
// with #415, and this keeps the same palette. Normalization follows
// matplotlib's _get_jacobi_norm: jrange falls back to 1.0 when all values are
// equal or only one exists (norm stays 0 → fixed blue-end color).

/** coolwarm 的 9 档采样（matplotlib.colormaps["coolwarm"] 等距取点）。 */
/** 9-stop sample of coolwarm (evenly sampled from matplotlib.colormaps["coolwarm"]). */
export const COOLWARM_STOPS = [
  "#3b4cc0",
  "#6282ea",
  "#8db0fe",
  "#b9d0f9",
  "#dddcdc",
  "#f5c4ac",
  "#f4987a",
  "#dd5f4b",
  "#b40426",
] as const;

/** Jacobi 常数归一化范围：[jmin, jmax, jrange]，jrange 防除零（全相等/空 → 1.0）。
 *  undefined 项（无 Jacobi 值的轨迹）不参与。空列表返回 (0, 1, 1)。 */
/** Normalization range of Jacobi constants: [jmin, jmax, jrange], jrange guarded
 *  against division by zero (1.0 when all-equal/empty). undefined entries
 *  (trajectories without a Jacobi value) do not participate; an empty list yields (0, 1, 1). */
export function jacobiNorm(values: readonly (number | undefined)[]): [number, number, number] {
  let jmin = Infinity;
  let jmax = -Infinity;
  for (const v of values) {
    if (v === undefined) continue;
    if (v < jmin) jmin = v;
    if (v > jmax) jmax = v;
  }
  if (!Number.isFinite(jmin)) return [0, 1, 1];
  return [jmin, jmax, jmax - jmin > 0 ? jmax - jmin : 1.0];
}

/** Jacobi 值 → 采样表线性插值色（hex）。归一化值钳到 [0, 1]。 */
/** Jacobi value → linearly interpolated sample-table color (hex); the
 *  normalized value is clamped to [0, 1]. */
export function jacobiColor(value: number, jmin: number, jrange: number): string {
  const norm = Math.min(1, Math.max(0, (value - jmin) / jrange));
  const pos = norm * (COOLWARM_STOPS.length - 1);
  const lo = Math.floor(pos);
  const hi = Math.min(lo + 1, COOLWARM_STOPS.length - 1);
  const t = pos - lo;
  const a = parseInt(COOLWARM_STOPS[lo].slice(1), 16);
  const b = parseInt(COOLWARM_STOPS[hi].slice(1), 16);
  const mix = (shift: number) =>
    Math.round(((a >> shift) & 0xff) * (1 - t) + ((b >> shift) & 0xff) * t);
  return `#${((mix(16) << 16) | (mix(8) << 8) | mix(0)).toString(16).padStart(6, "0")}`;
}
