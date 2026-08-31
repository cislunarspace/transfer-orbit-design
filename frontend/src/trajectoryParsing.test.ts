import { describe, expect, it } from "vitest";
import {
  framesToTrajectoryData,
  familyMembersToTrajectoryData,
  trajectoryTimeRange,
  transferTrajectoryToCanvasData,
  propagationToCanvasData,
  designEphemerisToCanvasData,
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

  it("CR3BP 帧产物逐条标注数据系 synodic_nd（#431）", () => {
    const got = framesToTrajectoryData(
      [
        { dtype: "f32", shape: [2, 3], data: [0, 1, 2, 3, 4, 5] },
        { dtype: "f32", shape: [2, 3], data: [6, 7, 8, 9, 10, 11] },
      ],
      {},
      MU,
    );
    expect(got.frames).toEqual(["synodic_nd", "synodic_nd"]);
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

describe("Jacobi 常数透传（#435）", () => {
  it("族成员 jacobi 透传进 TrajectoryData", () => {
    const states: number[] = [];
    for (let i = 0; i < 4; i++) states.push(i, i + 1, i + 2, 0, 0, 0);
    const got = familyMembersToTrajectoryData(
      [
        { states: [...states], times: [], period: null, jacobi: 3.1 },
        { states: [...states], times: [], period: null, jacobi: 2.9 },
      ],
      MU,
    );
    expect(got.jacobi).toEqual([3.1, 2.9]);
  });

  it("无 jacobi 的成员对应 undefined（与轨迹逐条对齐）", () => {
    const states: number[] = [];
    for (let i = 0; i < 4; i++) states.push(i, i + 1, i + 2, 0, 0, 0);
    const got = familyMembersToTrajectoryData(
      [
        { states: [...states], times: [], period: null, jacobi: 3.1 },
        { states: [...states], times: [], period: null },
      ],
      MU,
    );
    expect(got.jacobi).toEqual([3.1, undefined]);
  });

  it("被跳过的成员（缺 period 的初态）不占 jacobi 槽位", () => {
    const states: number[] = [];
    for (let i = 0; i < 4; i++) states.push(i, i + 1, i + 2, 0, 0, 0);
    const got = familyMembersToTrajectoryData(
      [
        { states: [...SEED.state], times: [], period: null, jacobi: 9.9 }, // 跳过
        { states: [...states], times: [], period: null, jacobi: 3.1 },
      ],
      MU,
    );
    expect(got.trajectories).toHaveLength(1);
    expect(got.jacobi).toEqual([3.1]);
  });

  it("成员 jacobi 缺失时回退记录级 recordJacobi（设计轨道单条通道）", () => {
    const states: number[] = [];
    for (let i = 0; i < 4; i++) states.push(i, i + 1, i + 2, 0, 0, 0);
    const got = familyMembersToTrajectoryData(
      [{ states: [...states], times: [], period: null }],
      MU,
      3.006,
    );
    expect(got.jacobi).toEqual([3.006]);
  });

  it("成员自带 jacobi 优先于记录级 recordJacobi", () => {
    const states: number[] = [];
    for (let i = 0; i < 4; i++) states.push(i, i + 1, i + 2, 0, 0, 0);
    const got = familyMembersToTrajectoryData(
      [{ states: [...states], times: [], period: null, jacobi: 3.1 }],
      MU,
      3.006,
    );
    expect(got.jacobi).toEqual([3.1]);
  });

  it("framesToTrajectoryData：orbits[i].jacobi 逐帧透传", () => {
    const pts: number[] = [];
    for (let i = 0; i < 6; i++) pts.push(i, i + 10, i + 20);
    const got = framesToTrajectoryData(
      [{ dtype: "f32", shape: [6, 3], data: pts }],
      { orbits: [{ jacobi: 3.05 }] },
      MU,
    );
    expect(got.jacobi).toEqual([3.05]);
  });

  it("framesToTrajectoryData：顶层 cr3bp_jacobi 只兜底单条轨迹", () => {
    const pts: number[] = [];
    for (let i = 0; i < 6; i++) pts.push(i, i + 10, i + 20);
    const single = framesToTrajectoryData(
      [{ dtype: "f32", shape: [6, 3], data: pts }],
      { cr3bp_jacobi: 3.006 },
      MU,
    );
    expect(single.jacobi).toEqual([3.006]);

    const multi = framesToTrajectoryData(
      [
        { dtype: "f32", shape: [3, 3], data: pts.slice(0, 9) },
        { dtype: "f32", shape: [3, 3], data: pts.slice(9) },
      ],
      { cr3bp_jacobi: 3.006 },
      MU,
    );
    expect(multi.jacobi).toEqual([undefined, undefined]);
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

  it("转移弧标注数据系 synodic_km（会合系物理 km，ADR 0040 契约）", () => {
    expect(transferTrajectoryToCanvasData(TRAJ, null).frames).toEqual(["synodic_km"]);
  });

  // —— 双几何段（#428 第二步，e2m2e 5.9.1 trajectory_gcrs_km）——
  // Dual-geometry segment (#428 step 2, e2m2e 5.9.1 trajectory_gcrs_km).
  const GCRS: number[][] = [
    [7000.0, 0.0, 100.0, 0.0, 7.0, 1.0],
    [0.0, 200000.0, 0.0, -1.0, 3.0, 0.0],
    [-384400.0, 0.0, 0.0, 0.0, 1.0, 0.0],
  ];

  it("gcrs 段同行对齐时携带惯性几何（位置 ÷DU_KM），主几何与时刻不变", () => {
    const got = transferTrajectoryToCanvasData(TRAJ, [0, 100, 200], undefined, "转移弧", GCRS);
    expect(got.inertialGeometries).toHaveLength(1);
    expect(got.inertialGeometries![0]![0]).toEqual([7000.0 / 384400, 0, 100.0 / 384400]);
    expect(got.inertialGeometries![0]![2]).toEqual([-1, 0, 0]);
    // 主几何仍是会合系段（会合视图逐项不变）；时刻共享 trajectory_times
    // The primary geometry stays the synodic segment (synodic view unchanged item
    // for item); times are shared with trajectory_times.
    expect(got.trajectories[0][2][0]).toBeCloseTo(380000 / 384400, 12);
    expect(got.times[0]).toEqual([0, 100, 200]);
    expect(got.frames).toEqual(["synodic_km"]);
  });

  it("gcrs 段行数不齐或缺位时惯性几何为 null/缺省（降级灰显口径）", () => {
    const misaligned = transferTrajectoryToCanvasData(TRAJ, null, undefined, "转移弧", GCRS.slice(0, 2));
    expect(misaligned.inertialGeometries![0]).toBeNull();
    // 未传参（low_thrust/旧响应）不带 inertialGeometries 字段
    // No param (low_thrust / legacy responses) leaves inertialGeometries absent.
    expect(transferTrajectoryToCanvasData(TRAJ, null).inertialGeometries).toBeUndefined();
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
    expect(got!.frames).toEqual(["inertial_km"]);
  });

  it("输入非法时返回 null（回退通用分支）", () => {
    expect(propagationToCanvasData(null, null)).toBeNull();
    expect(propagationToCanvasData([], [])).toBeNull();
    expect(propagationToCanvasData([384400.0], [2460800.5])).toBeNull();
  });
});

describe("designEphemerisToCanvasData 星历段解析", () => {
  // EphemerisTable 形状的星历段：会合无量纲位置 + UTC 分量
  const EPH = {
    synodic_position: [[1.1, 0.2, -0.3], [1.2, 0.3, -0.4]],
    year: [2024, 2024],
    month: [1, 1],
    day: [1, 1],
    hour: [0, 1],
    minute: [0, 0],
    second: [0, 0],
  };

  it("会合系无量纲直画（不缩放），UTC 分量 → et 基准", () => {
    const got = designEphemerisToCanvasData(EPH, "eph");
    expect(got).not.toBeNull();
    expect(got!.trajectories[0]).toEqual([[1.1, 0.2, -0.3], [1.2, 0.3, -0.4]]);
    expect(got!.timeBasis).toEqual(["et"]);
    expect(got!.times[0]).toHaveLength(2);
    // 相邻行差 1 小时（3600 s）
    expect(got!.times[0][1] - got!.times[0][0]).toBeCloseTo(3600, 3);
    expect(got!.labels).toEqual(["eph"]);
  });

  it("UTC 分量缺失/行数不齐 → 无时刻基准（轨迹仍上画布）", () => {
    const missing = { synodic_position: [[0, 0, 0]] };
    expect(designEphemerisToCanvasData(missing)).toEqual({
      trajectories: [[[0, 0, 0]]],
      times: [[]],
      timeBasis: ["none"],
      frames: ["synodic_nd"],
      labels: ["星历段（会合系）"],
    });
    const misaligned = { ...EPH, year: [2024] };
    expect(designEphemerisToCanvasData(misaligned)!.timeBasis).toEqual(["none"]);
  });

  it("synodic_position 非法时返回 null", () => {
    expect(designEphemerisToCanvasData(null)).toBeNull();
    expect(designEphemerisToCanvasData({})).toBeNull();
    expect(designEphemerisToCanvasData({ synodic_position: [] })).toBeNull();
    expect(designEphemerisToCanvasData({ synodic_position: [1, 2, 3] })).toBeNull();
  });

  it("星历段标注数据系 synodic_nd（会合系无量纲直画）", () => {
    expect(designEphemerisToCanvasData(EPH)!.frames).toEqual(["synodic_nd"]);
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
