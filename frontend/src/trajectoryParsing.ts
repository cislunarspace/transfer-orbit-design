// sidecar 帧/成员数据 → 画布轨迹（number[][][]，每条为 xyz 点列）+ 同源时刻数组。
//
// 帧解析优先用协议自带的 shape 区分 (n,6) 状态与 (n,3) 位置；
// (1,6) 是周期轨道初态，需要 period 才能在前端传播出整条轨迹，
// 缺 period 时跳过该成员，而不是只画一个点造成空画布。
//
// 时刻来源（行数与轨迹点数严格一致）：
// 传播路径按 period 均匀合成；帧数据优先 data.epochs；否则按行序兜底。

import { propagate } from "./cr3bp";
import type { FamilyMember } from "./sidecarApi";

export interface TrajectoryFrame {
  dtype: string;
  shape: number[];
  data: number[];
}

export interface TrajectoryData {
  trajectories: number[][][];
  /** 与 trajectories 逐条对齐的时刻数组（秒） */
  times: number[][];
}

/** 传播步数：与轨迹点数联动（点数 = 步数 + 1），时刻按 period/步数均匀合成 */
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

/** 通用工具响应帧 → 轨迹 + 时刻。data 提供 mu / orbits[i].period / period / epochs。 */
export function framesToTrajectoryData(
  frames: TrajectoryFrame[],
  data: Record<string, unknown>,
  defaultMu: number,
): TrajectoryData {
  const d = data as { mu?: unknown; orbits?: unknown[]; period?: unknown; epochs?: unknown };
  const mu = typeof d.mu === "number" ? d.mu : defaultMu;
  const orbits = Array.isArray(d.orbits) ? d.orbits : [];
  const epochs = Array.isArray(d.epochs) ? (d.epochs as unknown[]).map(Number) : null;
  const trajectories: number[][][] = [];
  const times: number[][] = [];

  frames.forEach((frame, i) => {
    const f = frame.data as number[];
    const rows = frame.shape[0] ?? 0;
    const cols = frame.shape[1] ?? 0;
    const period =
      Number((orbits[i] as { period?: unknown } | undefined)?.period) ||
      (typeof d.period === "number" ? d.period : null);

    if (rows === 1 && f.length === 6) {
      // 周期轨道初态：有 period 才能传播；缺则跳过
      if (period) {
        const pts = propagate(
          mu,
          { orbitId: `orbit-${i}`, mu, period, state: f.slice(0, 6) as [number, number, number, number, number, number] },
          PROPAGATION_STEPS,
        );
        trajectories.push(pts);
        times.push(linspaceByPeriod(period, pts.length));
      }
    } else if (cols === 6 || cols === 3) {
      const pts = chunksOf(f, cols, 3);
      trajectories.push(pts);
      times.push(matchingTimes(epochs, pts.length));
    } else if (frame.shape.length === 0 && f.length > 6 && f.length % 6 === 0) {
      const pts = chunksOf(f, 6, 3);
      trajectories.push(pts);
      times.push(matchingTimes(epochs, pts.length));
    } else if (frame.shape.length === 0 && f.length % 3 === 0) {
      const pts = chunksOf(f, 3, 3);
      trajectories.push(pts);
      times.push(matchingTimes(epochs, pts.length));
    }
  });
  return { trajectories, times };
}

/** epochs 行数匹配则用之，否则回退行序时刻；period 路径已单独合成。 */
function matchingTimes(times: number[] | null, points: number): number[] {
  if (times && times.length === points) return times;
  return rowIndexTimes(points);
}

/** 库记录的 familyMembers（(1,6) 初态或 (n,6) 状态）→ 轨迹 + 时刻。 */
export function familyMembersToTrajectoryData(members: FamilyMember[], mu: number): TrajectoryData {
  const trajectories: number[][][] = [];
  const times: number[][] = [];
  for (const [i, m] of members.entries()) {
    if (m.states.length === 6) {
      if (m.period) {
        const pts = propagate(
          mu,
          { orbitId: `member-${i}`, mu, period: m.period, state: m.states.slice(0, 6) as [number, number, number, number, number, number] },
          PROPAGATION_STEPS,
        );
        trajectories.push(pts);
        times.push(linspaceByPeriod(m.period, pts.length));
      }
    } else if (m.states.length > 6 && m.states.length % 6 === 0) {
      const pts = chunksOf(m.states, 6, 3);
      trajectories.push(pts);
      times.push(matchingTimes(m.times.map(Number), pts.length));
    } else if (m.states.length % 3 === 0) {
      const pts = chunksOf(m.states, 3, 3);
      trajectories.push(pts);
      times.push(matchingTimes(m.times.map(Number), pts.length));
    }
  }
  return { trajectories, times };
}

/** 全局时刻范围（多条轨迹取端点）；空则 null，时间轴保持禁用。 */
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
