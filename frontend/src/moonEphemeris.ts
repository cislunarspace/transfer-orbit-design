// 惯性视图（GCRS）的月球轨迹来源（#428 第一步，ADR 0013 决策 4）。
// 月球在质心归一会合系固定于 (1-mu, 0, 0) 且速度为零——这是会合系的
// 定义而非近似；经 sidecar spacetime_transform 的 synodic_to_j2000
// （旋转链由 SPICE 真实月历构造，特征长度随 et 脉动）换到地心 J2000
// 惯性 km，再 ÷DU_KM 归一进画布。J2000 与 GCRS 的差异是角秒级，远低于
// 可视化精度，视为同一惯性视图。
// The Moon's inertial track for the GCRS view (#428 step 1, ADR 0013
// decision 4). The Moon sits fixed at (1-mu, 0, 0) with zero velocity in
// the barycentric-normalized synodic frame — by definition, not
// approximation; the sidecar spacetime_transform's synodic_to_j2000 (the
// rotation chain built from the real SPICE lunar ephemeris, characteristic
// length pulsating with et) maps it to geocentric J2000 inertial km, then
// ÷DU_KM normalizes it onto the canvas. The J2000-vs-GCRS difference is
// arcsecond-level, far below visualization fidelity.

import { DU_KM, TU_SECONDS } from "./cr3bp";
import { etToJd } from "./timeBasis";

/** spacetime_convert 内部固定的地月质量比（algorithm/coordinate 的 MU_EM）。
 *  与画布 EARTH_MOON_MU 差 ~8e-8（×DU ≈ 0.03 km）；构造月球固定点时保持
 *  上游同值，变换链内部自洽。 */
/** The Earth-Moon mass ratio fixed inside spacetime_convert (MU_EM in
 *  algorithm/coordinate). Differs from the canvas EARTH_MOON_MU by ~8e-8
 *  (×DU ≈ 0.03 km); keep the upstream value here so the fixed point is
 *  self-consistent with the transform chain. */
export const E2M2E_MU = 0.0121506683;

/** 惯性视图的月球轨迹：DU 单位 xyz 点列，均匀采样覆盖 etRange（含端点）。
 *  idealized = true 标记 relative 钟下的理想化圆月（#477），渲染端据此
 *  标注「月球（理想化）」。 */
/** The Moon's track for the inertial view: xyz points in DU, uniformly
 *  sampled over etRange (endpoints included). idealized = true marks the
 *  idealized circular Moon under the relative clock (#477); the renderer
 *  labels it "Moon (idealized)" accordingly. */
export interface MoonTrack {
  points: number[][];
  etRange: [number, number];
  idealized?: boolean;
}

/** 采样数：每 0.02 TU（≈1.8 h）一点，下限 64、上限 400。0.02 TU 粒度上
 *  线性插值的弦高误差 ~15 km（3.8e-5 DU），不可见。 */
/** Sample count: one per 0.02 TU (≈1.8 h), floor 64, cap 400. The chord
 *  error of linear interpolation at 0.02 TU granularity is ~15 km
 *  (3.8e-5 DU) — invisible. */
export function moonSampleCount(etRange: [number, number]): number {
  const spanTu = (etRange[1] - etRange[0]) / TU_SECONDS;
  return Math.min(400, Math.max(64, Math.ceil(spanTu / 0.02) + 1));
}

/** relative 钟惯性视图的理想化圆月（#477）：地心 1 DU 圆轨道，θ = t
 * （时间轴数值即 TU 无量纲时刻，CR3BP ω=1），θ₀=0——与同屏理想化惯性段
 * （族轨道旋转 / 转移 gcrs 段）严格同约定。时间轴只有 et 钟产物时走
 * SPICE 真月轨迹，不用本函数。退化跨度（hi ≤ lo）返回 null。
 * 采样复用 moonSampleCount 的粒度口径。 */
/** The idealized circular Moon for the inertial view under the relative
 *  clock (#477): a 1 DU geocentric circle with θ = t (the timeline values
 *  ARE the TU dimensionless times, CR3BP ω=1), θ₀=0 — strictly the same
 *  convention as the on-screen idealized inertial segments (the family
 *  rotation / transfer gcrs segments). With any et-clock product on screen
 * the SPICE real track applies instead, never this function. A degenerate
 *  span (hi ≤ lo) returns null. Sampling reuses moonSampleCount's
 *  granularity. */
export function idealizedMoonTrack(range: [number, number]): MoonTrack | null {
  const [lo, hi] = range;
  if (!(hi > lo) || !Number.isFinite(lo) || !Number.isFinite(hi)) return null;
  // range 的数值即 TU，moonSampleCount 以 TU 计跨度，直接沿用
  // range values are TU; moonSampleCount already spans in TU — reuse as-is
  const n = moonSampleCount([lo, hi]);
  const points = Array.from({ length: n }, (_, i) => {
    const t = lo + ((hi - lo) * i) / (n - 1);
    return [Math.cos(t), Math.sin(t), 0];
  });
  return { points, etRange: [lo, hi], idealized: true };
}

/** synodic_to_j2000 请求参数：states 是月球会合系固定点（速度恒零），
 *  times 是无量纲会合时间 t_syn（0 = 参考历元），et0_jd 取时间轴跨度
 *  中点（t_syn 围绕 0 对称，数值性态最好）。 */
/** The synodic_to_j2000 request payload: states are the Moon's fixed
 *  synodic point (velocity identically zero), times are the dimensionless
 *  synodic times t_syn (0 = the reference epoch), and et0_jd takes the
 *  timeline span's midpoint (t_sym symmetric around 0 — best conditioning). */
export function moonTrackRequest(etRange: [number, number]): {
  states: number[][];
  times: number[];
  transform_type: string;
  et0_jd: number;
} {
  const n = moonSampleCount(etRange);
  const et0 = (etRange[0] + etRange[1]) / 2;
  const states = Array.from({ length: n }, () => [1 - E2M2E_MU, 0, 0, 0, 0, 0]);
  const times = Array.from(
    { length: n },
    (_, i) => (etRange[0] + ((etRange[1] - etRange[0]) * i) / (n - 1) - et0) / TU_SECONDS,
  );
  return { states, times, transform_type: "synodic_to_j2000", et0_jd: etToJd(et0) };
}

/** runTool 响应 → 月球轨迹：data.states 是 J2000 地心 km 状态序列，取
 *  位置 ÷DU_KM。error 信封由调用方先拦（resp.error 非空不进这里）；
 *  结构缺失、行残缺或含非有限值 → null（调用方降级：惯性视图无月球，
 *  ADR 0013 离线降级先例）。 */
/** A runTool response → the Moon track: data.states holds the geocentric
 *  J2000 km state sequence; positions ÷DU_KM. The caller intercepts the
 *  error envelope first (a non-null resp.error never reaches here);
 *  missing structure, truncated rows, or non-finite values → null (the
 *  caller degrades: no Moon in the inertial view, per the ADR 0013
 *  offline-degradation precedent). */
export function moonTrackFromResponse(
  data: unknown,
  etRange: [number, number],
): MoonTrack | null {
  const states = (data as { states?: unknown } | null)?.states;
  if (!Array.isArray(states) || states.length === 0) return null;
  const points: number[][] = [];
  for (const s of states) {
    if (!Array.isArray(s) || s.length < 3) return null;
    const p = [Number(s[0]), Number(s[1]), Number(s[2])];
    if (!p.every(Number.isFinite)) return null;
    points.push(p.map((v) => v / DU_KM));
  }
  return { points, etRange };
}

/** 月球轨迹上 et 时刻的位置（DU，线性插值）；et 为空或越界 → 端点/中点
 *  兜底。与轨迹时刻标记的「区间外隐藏」不同，月球是天体参照物，不因
 *  时刻越界而消失：越界取就近端点，无时刻取跨度中点。 */
/** The Moon's position (DU) at et on the track (linear interpolation);
 *  null/out-of-range et falls back to an endpoint/midpoint. Unlike the
 *  per-trajectory time markers that hide outside their spans, the Moon is
 *  a body reference — it never disappears: out-of-range clamps to the
 *  nearer endpoint, no-moment takes the span midpoint. */
export function moonPositionAt(track: MoonTrack, et: number | null): [number, number, number] {
  const [lo, hi] = track.etRange;
  const n = track.points.length;
  if (et === null || !Number.isFinite(et)) {
    return track.points[Math.floor((n - 1) / 2)] as [number, number, number];
  }
  const clamped = Math.min(hi, Math.max(lo, et));
  const alpha = hi > lo ? ((clamped - lo) / (hi - lo)) * (n - 1) : 0;
  const i = Math.min(n - 2, Math.max(0, Math.floor(alpha)));
  const t = alpha - i;
  const p0 = track.points[i];
  const p1 = track.points[i + 1] ?? track.points[i];
  return [
    p0[0] + (p1[0] - p0[0]) * t,
    p0[1] + (p1[1] - p0[1]) * t,
    p0[2] + (p1[2] - p0[2]) * t,
  ];
}
