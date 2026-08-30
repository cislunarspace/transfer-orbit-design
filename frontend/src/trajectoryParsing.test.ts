import { describe, expect, it } from "vitest";
import {
  framesToTrajectoryData,
  familyMembersToTrajectoryData,
  trajectoryTimeRange,
  transferTrajectoryToCanvasData,
  propagationToCanvasData,
  timelineMode,
  timesForMode,
  type TimeBasis,
} from "./trajectoryParsing";
import { etFromEpoch, etFromJdTdb } from "./timeBasis";

const MU = 0.01215058560962404;

/** 平圆参考轨道一个整周期附近的初态 + 周期，保证传播能闭合。 */
/** An initial state plus period around one full period of a flat circular reference orbit, so propagation closes. */
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
    // Six xyz points = 18 numbers; 18 % 6 === 0, so the old logic would have treated it as 3 state points.
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

describe("transferTrajectoryToCanvasData 转移轨迹解析", () => {
  // 会合系物理 km（e2m2e ADR 0040）：地月质心原点
  // Rotating-frame physical km (e2m2e ADR 0040): barycenter origin.
  const TRAJ = [
    [-4670.9, 6578.0, 0.0, 0.0, 7.8, 0.0],
    [100000.0, 0.0, 5000.0, 1.0, 0.0, 0.0],
    [380000.0, 0.0, 0.0, 0.0, 0.5, 0.0],
  ];

  it("位置 ÷DU_KM 归一（384400 km → 1 DU），速度列丢弃", () => {
    const got = transferTrajectoryToCanvasData(TRAJ, null);
    expect(got.trajectories).toHaveLength(1);
    expect(got.trajectories[0][0][0]).toBeCloseTo(-4670.9 / 384400, 12);
    expect(got.trajectories[0][2][0]).toBeCloseTo(380000 / 384400, 12);
    expect(got.trajectories[0][0]).toHaveLength(3);
  });

  it("trajectory_times 行数一致时透传（接时间轴）", () => {
    const got = transferTrajectoryToCanvasData(TRAJ, [0, 100, 200]);
    expect(got.times).toHaveLength(1);
    expect(got.times[0]).toEqual([0, 100, 200]);
  });

  it("times 缺失或行数不一致时丢弃（时间轴禁用）", () => {
    expect(transferTrajectoryToCanvasData(TRAJ, undefined).times).toEqual([]);
    expect(transferTrajectoryToCanvasData(TRAJ, [0, 1]).times).toEqual([]);
  });

  it("空轨迹返回空画布数据", () => {
    const got = transferTrajectoryToCanvasData([], []);
    expect(got.trajectories).toEqual([[]]);
    expect(got.times).toEqual([[]]);
  });

  it("给 tli_epoch（JD_TDB 数）时时刻平移到 et 绝对基准", () => {
    const jd = 2460800.5;
    const got = transferTrajectoryToCanvasData(TRAJ, [0, 100, 200], jd);
    expect(got.timeBasis).toEqual(["et"]);
    expect(got.times[0][0]).toBeCloseTo(etFromEpoch(jd), 6);
    expect(got.times[0][2]).toBeCloseTo(etFromEpoch(jd) + 200, 6);
  });

  it("给 tli_epoch（ISO UTC 字符串）时同样得到 et 基准", () => {
    const got = transferTrajectoryToCanvasData(TRAJ, [0, 100, 200], "2025-06-21T11:00:00");
    expect(got.timeBasis).toEqual(["et"]);
    expect(got.times[0][0]).toBeCloseTo(etFromEpoch("2025-06-21T11:00:00"), 6);
  });

  it("tli_epoch 缺失时保持 TLI 起算相对秒", () => {
    const got = transferTrajectoryToCanvasData(TRAJ, [0, 100, 200]);
    expect(got.timeBasis).toEqual(["relative"]);
    expect(got.times[0]).toEqual([0, 100, 200]);
  });

  it("图例标签可定制（缺省「转移弧」）", () => {
    expect(transferTrajectoryToCanvasData(TRAJ, null).labels).toEqual(["转移弧"]);
    expect(transferTrajectoryToCanvasData(TRAJ, null, undefined, "arc").labels).toEqual(["arc"]);
  });
});

describe("propagationToCanvasData 轨道预报解析（#421）", () => {
  it("position_km（GCRS km）÷DU_KM 缩放，times_jd_tdb → et 基准", () => {
    const got = propagationToCanvasData(
      [[384400.0, 0.0, 0.0], [0.0, 384400.0, 0.0]],
      [2460800.5, 2460801.5],
      "prop"
    );
    expect(got).not.toBeNull();
    expect(got!.trajectories[0][0]).toEqual([1, 0, 0]);
    expect(got!.timeBasis).toEqual(["et"]);
    expect(got!.times[0][0]).toBeCloseTo(etFromJdTdb(2460800.5), 6);
    expect(got!.labels).toEqual(["prop"]);
  });

  it("输入非法时返回 null（回退通用分支）", () => {
    expect(propagationToCanvasData(null, null)).toBeNull();
    expect(propagationToCanvasData([], [])).toBeNull();
    expect(propagationToCanvasData([384400.0], [2460800.5])).toBeNull();
  });
});

describe("timelineMode / timesForMode 两级时刻基准（ADR 0021 修订）", () => {
  const etData = {
    trajectories: [[[0, 0, 0]], [[1, 1, 1]]],
    times: [[100, 200], [0, 1]],
    timeBasis: ["et", "relative"] as TimeBasis[],
  };

  it("任一 et 产物在屏 → 全局 et 模式", () => {
    expect(timelineMode(etData)).toBe("et");
  });

  it("全部无 et 但有相对时刻 → 相对模式", () => {
    expect(timelineMode({ trajectories: [[], []], times: [[], [0, 1]], timeBasis: ["none", "relative"] })).toBe("relative");
  });

  it("全部无时刻 → null（时间轴禁用）", () => {
    expect(timelineMode({ trajectories: [[], []], times: [[], []], timeBasis: ["none", "none"] })).toBeNull();
  });

  it("et 模式下相对轨迹时刻置空（marker 隐藏），et 轨迹保留", () => {
    expect(timesForMode(etData, "et")).toEqual([[100, 200], []]);
  });

  it("相对模式保留全部时刻（旧行为）", () => {
    expect(timesForMode(etData, "relative")).toEqual(etData.times);
  });

  it("timeBasis 缺省按 relative 解释（兼容旧数据；et 模式下置空）", () => {
    const legacy = { trajectories: [[[0, 0, 0]]], times: [[0, 1]] };
    expect(timelineMode(legacy)).toBe("relative");
    expect(timesForMode(legacy, "relative")).toEqual([[0, 1]]);
    expect(timesForMode(legacy, "et")).toEqual([[]]);
  });
});
