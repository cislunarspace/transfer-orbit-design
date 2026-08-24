import { describe, expect, it } from "vitest";
import { familyMembersToTrajectories, framesToTrajectories } from "./trajectoryParsing";

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

describe("framesToTrajectories", () => {
  it("(n,3) 纯位置帧按 shape 解析，不误判为状态序列", () => {
    // 6 个 xyz 点 = 18 个数，18 % 6 === 0，旧逻辑会当成 3 个状态点
    const pts: number[] = [];
    for (let i = 0; i < 6; i++) pts.push(i, i + 10, i + 20);
    const got = framesToTrajectories(
      [{ dtype: "f32", shape: [6, 3], data: pts }],
      {},
      MU
    );
    expect(got).toHaveLength(1);
    expect(got[0]).toHaveLength(6);
    expect(got[0][0]).toEqual([0, 10, 20]);
  });

  it("(1,6) 初态帧有 period 时传播整条轨迹", () => {
    const got = framesToTrajectories(
      [{ dtype: "f32", shape: [1, 6], data: [...SEED.state] }],
      { orbits: [{ period: SEED.period }], mu: MU },
      MU
    );
    expect(got).toHaveLength(1);
    expect(got[0].length).toBeGreaterThan(100);
  });

  it("(1,6) 初态帧缺 period 时跳过，不产生单点轨迹", () => {
    const got = framesToTrajectories(
      [{ dtype: "f32", shape: [1, 6], data: [...SEED.state] }],
      {},
      MU
    );
    expect(got).toHaveLength(0);
  });

  it("(n,6) 状态帧按 shape 取 xyz", () => {
    const states: number[] = [];
    for (let i = 0; i < 4; i++) states.push(i, i + 1, i + 2, 0, 0, 0);
    const got = framesToTrajectories(
      [{ dtype: "f32", shape: [4, 6], data: states }],
      {},
      MU
    );
    expect(got[0]).toEqual([
      [0, 1, 2], [1, 2, 3], [2, 3, 4], [3, 4, 5],
    ]);
  });

  it("shape 缺失时回退长度启发式：恰 6 个数无 period 视为位置", () => {
    // 2 个 xyz 点 = 6 个数；无 period 可传播时不应只画 1 个点
    const got = framesToTrajectories(
      [{ dtype: "f32", shape: [], data: [1, 2, 3, 4, 5, 6] }],
      {},
      MU
    );
    expect(got[0]).toEqual([[1, 2, 3], [4, 5, 6]]);
  });
});

describe("familyMembersToTrajectories", () => {
  it("完整状态序列取 xyz", () => {
    const states: number[] = [];
    for (let i = 0; i < 4; i++) states.push(i, i + 1, i + 2, 0, 0, 0);
    const got = familyMembersToTrajectories([{ states, times: [], period: null }], MU);
    expect(got[0]).toEqual([[0, 1, 2], [1, 2, 3], [2, 3, 4], [3, 4, 5]]);
  });

  it("(1,6) 初态 + period 传播整条轨迹", () => {
    const got = familyMembersToTrajectories(
      [{ states: [...SEED.state], times: [], period: SEED.period }],
      MU
    );
    expect(got).toHaveLength(1);
    expect(got[0].length).toBeGreaterThan(100);
  });

  it("(1,6) 初态缺 period 时跳过，不产生单点轨迹", () => {
    const got = familyMembersToTrajectories(
      [{ states: [...SEED.state], times: [], period: null }],
      MU
    );
    expect(got).toHaveLength(0);
  });
});
