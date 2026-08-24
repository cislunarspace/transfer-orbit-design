// sidecar 帧/成员数据 → 画布轨迹（number[][][]，每条为 xyz 点列）。
//
// 帧解析优先用协议自带的 shape 区分 (n,6) 状态与 (n,3) 位置；
// (1,6) 是周期轨道初态，需要 period 才能在前端传播出整条轨迹，
// 缺 period 时跳过该成员，而不是只画一个点造成空画布。

import { propagate } from "./cr3bp";
import type { FamilyMember } from "./sidecarApi";

export interface TrajectoryFrame {
  dtype: string;
  shape: number[];
  data: number[];
}

function chunksOf(data: number[], size: number, take: number): number[][] {
  const pts: number[][] = [];
  for (let i = 0; i + size <= data.length; i += size) {
    pts.push(data.slice(i, i + take));
  }
  return pts;
}

/** 通用工具响应帧 → 轨迹列表。data 提供 mu / orbits[i].period / period。 */
export function framesToTrajectories(
  frames: TrajectoryFrame[],
  data: Record<string, unknown>,
  defaultMu: number,
): number[][][] {
  const d = data as { mu?: unknown; orbits?: unknown[]; period?: unknown };
  const mu = typeof d.mu === "number" ? d.mu : defaultMu;
  const orbits = Array.isArray(d.orbits) ? d.orbits : [];
  const trajectories: number[][][] = [];

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
        trajectories.push(propagate(mu, { orbitId: `orbit-${i}`, mu, period, state: f.slice(0, 6) as [number, number, number, number, number, number] }, 800));
      }
    } else if (cols === 6) {
      trajectories.push(chunksOf(f, 6, 3));
    } else if (cols === 3) {
      trajectories.push(chunksOf(f, 3, 3));
    } else if (frame.shape.length === 0 && f.length > 6 && f.length % 6 === 0) {
      trajectories.push(chunksOf(f, 6, 3));
    } else if (frame.shape.length === 0 && f.length % 3 === 0) {
      trajectories.push(chunksOf(f, 3, 3));
    }
  });
  return trajectories;
}

/** 库记录的 familyMembers（(1,6) 初态或 (n,6) 状态）→ 轨迹列表。 */
export function familyMembersToTrajectories(
  members: FamilyMember[],
  mu: number,
): number[][][] {
  const trajectories: number[][][] = [];
  for (const [i, m] of members.entries()) {
    if (m.states.length === 6) {
      if (m.period) {
        trajectories.push(
          propagate(mu, { orbitId: `member-${i}`, mu, period: m.period, state: m.states.slice(0, 6) as [number, number, number, number, number, number] }, 800),
        );
      }
    } else if (m.states.length > 6 && m.states.length % 6 === 0) {
      trajectories.push(chunksOf(m.states, 6, 3));
    } else if (m.states.length % 3 === 0) {
      trajectories.push(chunksOf(m.states, 3, 3));
    }
  }
  return trajectories;
}
