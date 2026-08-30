// sidecar 帧/成员数据 → 画布轨迹（number[][][]，每条为 xyz 点列）+ 同源时刻数组。
//
// 帧解析优先用协议自带的 shape 区分 (n,6) 状态与 (n,3) 位置；
// (1,6) 是周期轨道初态，需要 period 才能在前端传播出整条轨迹，
// 缺 period 时跳过该成员，而不是只画一个点造成空画布。
//
// 时刻来源（行数与轨迹点数严格一致）与基准（timeBasis，ADR 0021 修订）：
// et = J2000 起算真实历元秒（时间轴绝对基准）；relative = 相对时刻
// （period 合成 / 行序），仅当同屏无 et 产物时参与走查；none = 无时刻。
// sidecar frame/member data → canvas trajectories (number[][][], each an xyz point list) plus a matching
// time array.
//
// Frame parsing prefers the protocol-provided shape to tell (n,6) states from (n,3) positions; a (1,6)
// entry is a periodic-orbit initial state needing a period to propagate the full trajectory in the frontend;
// members without a period are skipped rather than drawn as a single point on an empty canvas.
//
// Time sources (row counts match trajectory point counts exactly) and their bases (timeBasis, ADR 0021
// revision): et = true epoch seconds since J2000 (the timeline's absolute basis); relative = relative time
// (period-synthesized / row order), walks only when no et product is on screen; none = no timing.

import { DU_KM, propagate } from "./cr3bp";
import { etFromEpoch, etFromJdTdb } from "./timeBasis";
import type { FamilyMember } from "./sidecarApi";

export interface TrajectoryFrame {
  dtype: string;
  shape: number[];
  data: number[];
}

/** 单条轨迹的时刻基准：et=真实历元秒；relative=相对时刻；none=无时刻 */
/** Per-trajectory time basis: et = true epoch seconds; relative = relative time; none = untimed. */
export type TimeBasis = "et" | "relative" | "none";

/** 单条轨迹的数据系标签（CONTEXT.md「数据系」枚举的画布子集；视图系是
 *  用户显示选择，不随数据走，故不在此列）。与 e2m2e state_frame 词表的
 *  对应：synodic_nd ≈ synodic_barycentric_nd、synodic_km ≈
 *  synodic_barycentric_km、inertial_km ≈ 地心惯性 km（GCRS）。
 *  A trajectory's data-frame tag (the canvas subset of CONTEXT.md's
 *  数据系 enum; the view frame is a display choice and never rides the
 *  data). Maps onto e2m2e's state_frame vocabulary as noted. */
export type DataFrameTag = "synodic_nd" | "synodic_km" | "inertial_km";

export interface TrajectoryData {
  trajectories: number[][][];
  /** 与 trajectories 逐条对齐的时刻数组（秒；无时刻为空数组） */
  /** Time array aligned row-by-row with trajectories (seconds; empty when untimed). */
  times: number[][];
  /** 与 trajectories 逐条对齐的时刻基准；缺省按 relative 解释（兼容旧调用） */
  /** Time basis aligned row-by-row; defaults to relative for legacy callers. */
  timeBasis?: TimeBasis[];
  /** 与 trajectories 逐条对齐的数据系标签；缺省按 synodic_nd 解释
   *  （画布既有轨迹全部是会合系无量纲，惯性系轨迹自带标签） */
  /** Data-frame tag aligned row-by-row; defaults to synodic_nd (every legacy
   *  canvas trajectory is synodic dimensionless; inertial ones self-tag). */
  frames?: DataFrameTag[];
  /** 与 trajectories 逐条对齐的图例标签；缺省不进图例 */
  /** Legend label per trajectory; omitted entries stay out of the legend. */
  labels?: string[];
  /** 与 trajectories 逐条对齐的 Jacobi 常数；undefined 项 = 该轨迹无
   *  Jacobi 值（转移弧等），渲染时回退色环（#435）。 */
  /** Jacobi constant aligned row-by-row; undefined entries = no Jacobi
   *  value (transfer arcs etc.), falling back to the color cycle (#435). */
  jacobi?: (number | undefined)[];
}

/** 传播步数：与轨迹点数联动（点数 = 步数 + 1），时刻按 period/步数均匀合成 */
/** Propagation steps: linked to the trajectory point count (points = steps + 1); times synthesize uniformly over period/steps. */
const PROPAGATION_STEPS = 800;

function chunksOf(data: number[], size: number, take: number): number[][] {
  const pts: number[][] = [];
  for (let i = 0; i + size <= data.length; i += size) {
    pts.push(data.slice(i, i + take));
  }
  return pts;
}

function linspaceByPeriod(period: number, points: number): number[] {
  return Array.from({ length: points }, (_, i) => (i * period) / (points - 1));
}

function rowIndexTimes(points: number): number[] {
  return Array.from({ length: points }, (_, i) => i);
}

/** 有限数值才收：NaN/Infinity/非 number 一律视为无 Jacobi 值。 */
/** Accept only finite numbers: NaN/Infinity/non-numbers all count as no Jacobi value. */
function finiteOrUndefined(v: unknown): number | undefined {
  return typeof v === "number" && Number.isFinite(v) ? v : undefined;
}

/** 通用工具响应帧 → 轨迹 + 时刻。data 提供 mu / orbits[i].period / period / epochs。 */
/** Generic tool response frame → trajectories + times. data provides mu / orbits[i].period / period / epochs. */
export function framesToTrajectoryData(
  frames: TrajectoryFrame[],
  data: Record<string, unknown>,
  defaultMu: number,
): TrajectoryData {
  const d = data as {
    mu?: unknown;
    orbits?: unknown[];
    period?: unknown;
    epochs?: unknown;
    cr3bp_jacobi?: unknown;
  };
  const mu = typeof d.mu === "number" ? d.mu : defaultMu;
  const orbits = Array.isArray(d.orbits) ? d.orbits : [];
  const epochs = Array.isArray(d.epochs) ? (d.epochs as unknown[]).map(Number) : null;
  const trajectories: number[][][] = [];
  const times: number[][] = [];
  const timeBasis: TimeBasis[] = [];
  const frameTags: DataFrameTag[] = [];
  const jacobi: (number | undefined)[] = [];

  frames.forEach((frame, i) => {
    const f = frame.data as number[];
    const rows = frame.shape[0] ?? 0;
    const cols = frame.shape[1] ?? 0;
    const orbit = orbits[i] as { period?: unknown; jacobi?: unknown } | undefined;
    const period =
      Number(orbit?.period) ||
      (typeof d.period === "number" ? d.period : null);
    const orbitJacobi = finiteOrUndefined(orbit?.jacobi);

    if (rows === 1 && f.length === 6) {
      // 周期轨道初态：有 period 才能传播；缺则跳过
      // Periodic-orbit initial state: propagatable only with a period; skipped when absent.
      if (period) {
        const pts = propagate(
          mu,
          { orbitId: `orbit-${i}`, mu, period, state: f.slice(0, 6) as [number, number, number, number, number, number] },
          PROPAGATION_STEPS,
        );
        trajectories.push(pts);
        times.push(linspaceByPeriod(period, pts.length));
        timeBasis.push("relative");
        frameTags.push("synodic_nd");
        jacobi.push(orbitJacobi);
      }
    } else if (cols === 6 || cols === 3) {
      const pts = chunksOf(f, cols, 3);
      trajectories.push(pts);
      times.push(matchingTimes(epochs, pts.length));
      timeBasis.push("relative");
      frameTags.push("synodic_nd");
      jacobi.push(orbitJacobi);
    } else if (frame.shape.length === 0 && f.length > 6 && f.length % 6 === 0) {
      const pts = chunksOf(f, 6, 3);
      trajectories.push(pts);
      times.push(matchingTimes(epochs, pts.length));
      timeBasis.push("relative");
      frameTags.push("synodic_nd");
      jacobi.push(orbitJacobi);
    } else if (frame.shape.length === 0 && f.length % 3 === 0) {
      const pts = chunksOf(f, 3, 3);
      trajectories.push(pts);
      times.push(matchingTimes(epochs, pts.length));
      timeBasis.push("relative");
      frameTags.push("synodic_nd");
      jacobi.push(orbitJacobi);
    }
  });
  // 设计直出（DesignOrbitResponse）的顶层 cr3bp_jacobi 是单条轨道的值，
  // 只有本次恰产出一条轨迹时才能归属，多条时归属不明则不填。
  // A design response's top-level cr3bp_jacobi (DesignOrbitResponse) belongs to a
  // single orbit: it applies only when exactly one trajectory came out this round.
  const topJacobi = finiteOrUndefined(d.cr3bp_jacobi);
  if (topJacobi !== undefined && jacobi.length === 1 && jacobi[0] === undefined) {
    jacobi[0] = topJacobi;
  }
  return { trajectories, times, timeBasis, frames: frameTags, jacobi };
}

/** epochs 行数匹配则用之，否则回退行序时刻；period 路径已单独合成。 */
/** Uses epochs when the row count matches, else falls back to row-order times; the period path synthesizes its own. */
function matchingTimes(times: number[] | null, points: number): number[] {
  if (times && times.length === points) return times;
  return rowIndexTimes(points);
}

/** 转移设计响应的 trajectory（(n,6) 会合系物理 km/km/s，e2m2e ADR 0040 契约）
 *  → 画布轨迹：位置 ÷DU_KM 归一到会合无量纲。trajectory_times（TLI 起算秒）
 *  与行数一致则作同源时刻接时间轴，否则丢弃（时间轴禁用）。给出 tli_epoch
 *  时时刻平移到 et 绝对基准（ADR 0021 修订：et 是时间轴唯一绝对基准），
 *  否则保持 TLI 起算相对秒。 */
/** transfer_design trajectory ((n,6) rotating-frame physical km/km/s, the
 *  e2m2e ADR 0040 contract) → canvas data: positions normalized by DU_KM.
 *  trajectory_times (seconds since TLI) pass through as matching times when
 *  row-aligned, else dropped (timeline stays disabled). With tli_epoch given,
 *  times shift onto the et absolute basis (ADR 0021 revision: et is the
 *  timeline's only absolute basis); otherwise they stay TLI-relative. */
export function transferTrajectoryToCanvasData(
  trajectory: number[][],
  times: unknown,
  tliEpoch?: string | number,
  label = "转移弧",
): TrajectoryData {
  const pts = trajectory.map((row) => [
    Number(row[0]) / DU_KM,
    Number(row[1]) / DU_KM,
    Number(row[2]) / DU_KM,
  ]);
  const aligned =
    Array.isArray(times) && times.length === trajectory.length
      ? (times as unknown[]).map(Number)
      : null;
  const tliEt = tliEpoch !== undefined ? etFromEpoch(tliEpoch) : NaN;
  const etTimes =
    aligned && Number.isFinite(tliEt) ? aligned.map((t) => t + tliEt) : null;
  return {
    trajectories: [pts],
    times: etTimes ? [etTimes] : aligned ? [aligned] : [],
    timeBasis: [etTimes ? "et" : aligned ? "relative" : "none"],
    frames: ["synodic_km"],
    labels: [label],
  };
}

/** 轨道预报响应 → 画布轨迹（#421 修复）。position_km 是 GCRS 惯性 km，
 *  ÷DU_KM 缩放后画的是惯性系几何形状（会合系视图下方向不随地球-月球线
 *  旋转，待惯性视图落地前如实标注）；times_jd_tdb → et 绝对基准。
 *  state_frame 契约（e2m2e ADR 0040 增补）到位后按标签替换此硬编码。 */
/** Orbit-propagation response → canvas data (#421 fix). position_km is GCRS
 *  inertial km: after ÷DU_KM scaling the drawn shape is inertial-frame
 *  geometry (directions do not co-rotate with the Earth-Moon line in the
 *  synodic view — labeled honestly until the inertial view lands);
 *  times_jd_tdb → the et absolute basis. Replace this hardcode by the
 *  state_frame label once that contract (e2m2e ADR 0040 amendment) ships. */
export function propagationToCanvasData(
  positionKm: unknown,
  timesJdTdb: unknown,
  label = "轨道预报（惯性系几何）",
): TrajectoryData | null {
  if (!Array.isArray(positionKm) || positionKm.length === 0 || !Array.isArray(positionKm[0])) {
    return null;
  }
  const pts = (positionKm as number[][]).map((p) => [
    Number(p[0]) / DU_KM,
    Number(p[1]) / DU_KM,
    Number(p[2]) / DU_KM,
  ]);
  const jds = Array.isArray(timesJdTdb) ? (timesJdTdb as unknown[]).map(Number) : null;
  const etTimes =
    jds && jds.length === pts.length && jds.every((v) => Number.isFinite(v))
      ? jds.map((jd) => etFromJdTdb(jd))
      : null;
  return {
    trajectories: [pts],
    times: etTimes ? [etTimes] : [],
    timeBasis: [etTimes ? "et" : "none"],
    frames: ["inertial_km"],
    labels: [label],
  };
}

/** EphemerisTable 的 UTC 分量（year..second 各 (n,)）→ et 秒数组；分量缺失、
 *  行数与 n 不齐或含非有限值 → null（该轨迹保持无时刻基准）。导出供
 *  catalogApi 复用（catalog_get 记录的 eph/ 段与 EphemerisTable 同形）。 */
/** EphemerisTable's UTC components (year..second, each (n,)) → et seconds;
 *  null when components are missing, misaligned with n, or non-finite.
 *  Exported for catalogApi (the catalog_get record's eph/ segment shares
 *  EphemerisTable's shape). */
export function ephemerisUtcToEt(ephemeris: Record<string, unknown>, n: number): number[] | null {
  const parts = ["year", "month", "day", "hour", "minute", "second"].map(
    (k) => ephemeris[k],
  ) as unknown[][];
  if (parts.some((p) => !Array.isArray(p) || p.length !== n)) return null;
  const p2 = (v: unknown) => String(Math.trunc(Number(v))).padStart(2, "0");
  const out = (parts[0] as unknown[]).map((_, i) =>
    etFromEpoch(
      `${p2(parts[0][i])}-${p2(parts[1][i])}-${p2(parts[2][i])}T` +
        `${p2(parts[3][i])}:${p2(parts[4][i])}:${p2(parts[5][i])}`,
    ),
  );
  return out.every(Number.isFinite) ? out : null;
}

/** 设计响应 / 库记录的星历段 → 画布轨迹（修"画布只见周期曲线"）。
 *  synodic_position 是地月会合系无量纲 (n,3)——画布原生系，直画不缩放；
 *  UTC 分量行数对齐则逐行合成 et 绝对基准（ADR 0021）。GCRS position_km
 *  不在此画（惯性几何，预报链路 propagationToCanvasData 已管）。
 *  入参与 e2m2e EphemerisTable 字段同名（设计响应 ephemeris dict 与库记录
 *  eph/ 段同形）。 */
/** A design response / catalog record's ephemeris segment → canvas data
 *  (fixes "canvas shows only the periodic curve"). synodic_position is the
 *  Earth-Moon synodic-frame dimensionless (n,3) — the canvas' native frame,
 *  drawn as-is without scaling; row-aligned UTC components compose the et
 *  absolute basis (ADR 0021). GCRS position_km is not drawn here (inertial
 *  geometry belongs to the propagation path). Field names match e2m2e's
 *  EphemerisTable (the design response ephemeris dict and the record eph/
 *  segment share the shape). */
export function designEphemerisToCanvasData(
  ephemeris: Record<string, unknown> | null | undefined,
  label = "星历段（会合系）",
): TrajectoryData | null {
  const rows = ephemeris?.synodic_position;
  if (!Array.isArray(rows) || rows.length === 0 || !Array.isArray(rows[0])) {
    return null;
  }
  const pts = (rows as unknown[]).map((p) => {
    const r = p as number[];
    return [Number(r[0]), Number(r[1]), Number(r[2])];
  });
  const etTimes = ephemerisUtcToEt(ephemeris as Record<string, unknown>, pts.length);
  return {
    trajectories: [pts],
    times: [etTimes ?? []],
    timeBasis: [etTimes ? "et" : "none"],
    frames: ["synodic_nd"],
    labels: [label],
  };
}

/** 库记录的 familyMembers（(1,6) 初态或 (n,6) 状态）→ 轨迹 + 时刻。
 *  recordJacobi 是记录级 Jacobi（设计轨道等单条记录），成员未自带
 *  jacobi 时兜底；成员值优先（族记录逐成员各异，CONTEXT.md 族记录）。 */
/** A catalog record's familyMembers ((1,6) initial states or (n,6) states) →
 *  trajectories + times. recordJacobi is the record-level Jacobi (single-orbit
 *  design records), falling back only when a member carries none; a member's
 *  own value wins (family records differ member-by-member). */
export function familyMembersToTrajectoryData(
  members: FamilyMember[],
  mu: number,
  recordJacobi?: number | null,
): TrajectoryData {
  const trajectories: number[][][] = [];
  const times: number[][] = [];
  const timeBasis: TimeBasis[] = [];
  const frameTags: DataFrameTag[] = [];
  const jacobi: (number | undefined)[] = [];
  const fallback = finiteOrUndefined(recordJacobi);
  for (const [i, m] of members.entries()) {
    const memberJacobi = finiteOrUndefined(m.jacobi) ?? fallback;
    if (m.states.length === 6) {
      if (m.period) {
        const pts = propagate(
          mu,
          { orbitId: `member-${i}`, mu, period: m.period, state: m.states.slice(0, 6) as [number, number, number, number, number, number] },
          PROPAGATION_STEPS,
        );
        trajectories.push(pts);
        times.push(linspaceByPeriod(m.period, pts.length));
        timeBasis.push("relative");
        frameTags.push("synodic_nd");
        jacobi.push(memberJacobi);
      }
    } else if (m.states.length > 6 && m.states.length % 6 === 0) {
      const pts = chunksOf(m.states, 6, 3);
      trajectories.push(pts);
      times.push(matchingTimes(m.times.map(Number), pts.length));
      timeBasis.push("relative");
      frameTags.push("synodic_nd");
      jacobi.push(memberJacobi);
    } else if (m.states.length % 3 === 0) {
      const pts = chunksOf(m.states, 3, 3);
      trajectories.push(pts);
      times.push(matchingTimes(m.times.map(Number), pts.length));
      timeBasis.push("relative");
      frameTags.push("synodic_nd");
      jacobi.push(memberJacobi);
    }
  }
  return { trajectories, times, timeBasis, frames: frameTags, jacobi };
}

/** 全局时刻范围（多条轨迹取端点）；空则 null，时间轴保持禁用。 */
/** Global time range (endpoints across trajectories); null when empty, keeping the timeline disabled. */
export function trajectoryTimeRange(times: number[][]): [number, number] | null {
  if (times.length === 0) return null;
  let min = Infinity;
  let max = -Infinity;
  for (const t of times) {
    if (t.length === 0) continue;
    if (t[0] < min) min = t[0];
    if (t[t.length - 1] > max) max = t[t.length - 1];
  }
  return Number.isFinite(min) && Number.isFinite(max) ? [min, max] : null;
}

/** 时间轴的全局时刻模式（ADR 0021 修订）：任一 et 产物在屏 → 全局 et 钟；
 *  全部无 et 但存在相对时刻 → 相对模式；否则 null（时间轴禁用）。
 *  相对与绝对不混排：et 模式下相对/无基准轨迹不参与时刻走查。 */
/** The timeline's global time mode (ADR 0021 revision): any et product on
 *  screen → global et clock; relative times with no et → relative mode;
 *  otherwise null (timeline disabled). Relative and absolute never mix: in
 *  et mode, relative/untimed trajectories stay out of the time walkthrough. */
export function timelineMode(data: TrajectoryData): "et" | "relative" | null {
  const basis = data.timeBasis ?? data.trajectories.map(() => "relative" as TimeBasis);
  if (basis.includes("et")) return "et";
  const hasRelative = data.times.some((t) => t.length > 0);
  return hasRelative ? "relative" : null;
}

/** et 模式下的画布时刻数据：et 轨迹保留时刻，其余置空（marker 隐藏）。 */
/** Canvas time data in et mode: keep et trajectories' times, blank the rest (markers hide). */
export function timesForMode(data: TrajectoryData, mode: "et" | "relative" | null): number[][] {
  if (mode === null) return data.times.map(() => []);
  const basis = data.timeBasis ?? data.trajectories.map(() => "relative" as TimeBasis);
  return data.times.map((t, i) => (mode === "et" && basis[i] !== "et" ? [] : t));
}
