// 画布轨迹拾取（#452）的纯判定逻辑：与 three.js 解耦，便于单测。
// Pure decision logic for canvas trajectory picking (#452): decoupled from
// three.js so it stays unit-testable.

/** 一次拾取命中的最小描述：轨迹线序号（绘制顺序，与 labels 对齐）+ 相交距离。 */
/** Minimal pick-hit descriptor: trajectory-line index (draw order, aligned
 *  with labels) plus the intersection distance. */
export interface PickHit {
  index: number;
  distance: number;
}

/** 从 Raycaster 命中列表取最近轨迹：剔除无效距离与非法序号；空/全无效返回 null。 */
/** Pick the nearest trajectory from a raycaster hit list: invalid distances
 *  and bad indices are dropped; empty or all-invalid yields null. */
export function pickNearestTrajectory(hits: PickHit[]): number | null {
  let best: PickHit | null = null;
  for (const h of hits) {
    if (!Number.isFinite(h.distance) || h.index < 0) continue;
    if (!best || h.distance < best.distance) best = h;
  }
  return best ? best.index : null;
}

/** 拾取阈值由轨迹包围盒尺寸按比例推导并夹紧：大场景不至于误吞邻居，
 *  小场景不至于必须精确点线；非法尺寸回落默认值。 */
/** The pick threshold scales with the trajectory bounding-box size and is
 *  clamped: large scenes must not swallow neighbours, small ones must not
 *  demand pixel-exact clicks; invalid sizes fall back to the default. */
export function pickThresholdFromSize(size: number): number {
  if (!Number.isFinite(size) || size <= 0) return 0.02;
  return Math.min(0.15, Math.max(0.005, size * 0.02));
}
