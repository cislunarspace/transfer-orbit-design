import { describe, expect, it } from "vitest";
import {
  framesToTrajectoryData,
  familyMembersToTrajectoryData,
  trajectoryTimeRange,
} from "./trajectoryParsing";

const MU = 0.01215058560962404;

/** 平圆参考轨道一个整周期附近的初态 + 周期，保证传播能闭合。 */
const SEED = {
  orbitId: "t",
  mu: MU,
  period: 2.16,
  state: [
    0.5, 0.8660254037844386, 0.0,
    -0.8660254037844386, 0.5, 0.0,
  ] as [number, number, number, number, number, number],
};

describe("framesToTrajectoryData 轨迹解析", () => {
  it("(n,3) 纯位置帧按 shape 解析，不误判为状态序列", () => {
    // 6 个 xyz 点 = 18 个数，18 % 6 === 0，旧逻辑会当成 3 个状态点
    const pts: number[] = [];
    for (let i = 0; i < 6; i++) pts.push(i, i + 10, i + 20);
    const got = framesToTrajectoryData([{ dtype: "f32", shape: [6, 3], data: pts }], {}, MU);
    expect(got.trajectories).toHaveLength(1);
    expect(got.trajectories[0]).toHaveLength(6);
    expect(got.trajectories[0][0]).toEqual([0, 10, 20]);
  });

  it("(1,6) 初态帧有 period 时传播整条轨迹，时刻按 period 均匀合成", () => {
    const got = framesToTrajectoryData(
      [{ dtype: "f32", shape: [1, 6], data: [...SEED.state] }],
      { orbits: [{ period: SEED.period }], mu: MU },
      MU,
    );
    expect(got.trajectories).toHaveLength(1);
    expect(got.trajectories[0].length).toBeGreaterThan(100);
    const t = got.times[0];
    expect(t).toHaveLength(got.trajectories[0].length);
    expect(t[0]).toBeCloseTo(0, 10);
    expect(t[t.length - 1]).toBeCloseTo(SEED.period, 10);
  });

  it("(1,6) 初态帧缺 period 时跳过，不产生单点轨迹", () => {
    const got = framesToTrajectoryData([{ dtype: "f32", shape: [1, 6], data: [...SEED.state] }], {}, MU);
    expect(got.trajectories).toHaveLength(0);
    expect(got.times).toHaveLength(0);
  });

  it("(n,6) 状态帧按 shape 取 xyz，data.epochs 提供时刻", () => {
    const states: number[] = [];
    for (let i = 0; i < 4; i++) states.push(i, i + 1, i + 2, 0, 0, 0);
    const epochs = [100, 200, 300, 400];
    const got = framesToTrajectoryData(
      [{ dtype: "f32", shape: [4, 6], data: states }],
      { epochs },
      MU,
    );
    expect(got.trajectories[0]).toEqual([
      [0, 1, 2], [1, 2, 3], [2, 3, 4], [3, 4, 5],
    ]);
    expect(got.times[0]).toEqual(epochs);
  });

  it("epochs 行数不匹配时回退行序时刻", () => {
    const states: number[] = [];
    for (let i = 0; i < 4; i++) states.push(i, i + 1, i + 2, 0, 0, 0);
    const got = framesToTrajectoryData(
      [{ dtype: "f32", shape: [4, 6], data: states }],
      { epochs: [1, 2] }, // 只有 2 个，行数不匹配
      MU,
    );
    expect(got.times[0]).toEqual([0, 1, 2, 3]);
  });

  it("无 epochs 的帧按行序合成相对时刻", () => {
    const pts: number[] = [];
    for (let i = 0; i < 3; i++) pts.push(i, i, i);
    const got = framesToTrajectoryData([{ dtype: "f32", shape: [3, 3], data: pts }], {}, MU);
    expect(got.times[0]).toEqual([0, 1, 2]);
  });

  it("shape 缺失时回退长度启发式：恰 6 个数无 period 视为位置", () => {
    const got = framesToTrajectoryData([{ dtype: "f32", shape: [], data: [1, 2, 3, 4, 5, 6] }], {}, MU);
    expect(got.trajectories[0]).toEqual([[1, 2, 3], [4, 5, 6]]);
  });
});

describe("familyMembersToTrajectoryData 轨迹解析", () => {
  it("完整状态序列取 xyz，成员 times 提供时刻", () => {
    const states: number[] = [];
    const times: number[] = [];
    for (let i = 0; i < 4; i++) {
      states.push(i, i + 1, i + 2, 0, 0, 0);
      times.push(i * 10);
    }
    const got = familyMembersToTrajectoryData([{ states, times, period: null }], MU);
    expect(got.trajectories[0]).toEqual([
      [0, 1, 2], [1, 2, 3], [2, 3, 4], [3, 4, 5],
    ]);
    expect(got.times[0]).toEqual(times);
  });

  it("(1,6) 初态 + period 传播整条轨迹，时刻按 period 合成", () => {
    const got = familyMembersToTrajectoryData(
      [{ states: [...SEED.state], times: [], period: SEED.period }],
      MU,
    );
    expect(got.trajectories).toHaveLength(1);
    expect(got.trajectories[0].length).toBeGreaterThan(100);
    const t = got.times[0];
    expect(t).toHaveLength(got.trajectories[0].length);
    expect(t[t.length - 1]).toBeCloseTo(SEED.period, 10);
  });

  it("(1,6) 初态缺 period 时跳过，不产生单点轨迹", () => {
    const got = familyMembersToTrajectoryData([{ states: [...SEED.state], times: [], period: null }], MU);
    expect(got.trajectories).toHaveLength(0);
  });

  it("成员 times 行数不匹配时回退行序时刻", () => {
    const states: number[] = [];
    for (let i = 0; i < 4; i++) states.push(i, i + 1, i + 2, 0, 0, 0);
    const got = familyMembersToTrajectoryData([{ states, times: [1], period: null }], MU);
    expect(got.times[0]).toEqual([0, 1, 2, 3]);
  });
});

describe("trajectoryTimeRange", () => {
  it("多条时刻取全局端点", () => {
    expect(trajectoryTimeRange([[0, 1, 2], [5, 10]])).toEqual([0, 10]);
  });

  it("空列表返回 null（时间轴禁用）", () => {
    expect(trajectoryTimeRange([])).toBeNull();
  });
});
