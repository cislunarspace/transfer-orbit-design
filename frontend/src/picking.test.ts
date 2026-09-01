// 拾取命中筛选单测（#452）：Raycaster 可能命中多条轨迹线，取距离最近者；
// 无效距离（NaN/Infinity）与非法序号剔除；空命中返回 null。
// Pick-hit filtering unit tests (#452): the raycaster may hit several
// trajectory lines — keep the nearest; invalid distances and bad indices are
// dropped; empty hits yield null.

import { describe, it, expect } from "vitest";
import { pickNearestTrajectory, pickThresholdFromSize } from "./picking";

describe("pickNearestTrajectory（#452）", () => {
  it("命中多条取距离最近者", () => {
    expect(
      pickNearestTrajectory([
        { index: 0, distance: 5 },
        { index: 2, distance: 1.5 },
        { index: 1, distance: 3 },
      ]),
    ).toBe(2);
  });

  it("剔除 NaN/Infinity 距离与负序号，再取最近", () => {
    expect(
      pickNearestTrajectory([
        { index: 0, distance: NaN },
        { index: 1, distance: Infinity },
        { index: -1, distance: 0.1 },
        { index: 3, distance: 2 },
      ]),
    ).toBe(3);
  });

  it("空命中或全部无效返回 null", () => {
    expect(pickNearestTrajectory([])).toBeNull();
    expect(pickNearestTrajectory([{ index: 0, distance: NaN }])).toBeNull();
  });
});

describe("pickThresholdFromSize（#452）", () => {
  it("按包围盒尺寸的比例取值", () => {
    expect(pickThresholdFromSize(10)).toBeCloseTo(0.15, 10); // 10 × 0.02 = 0.2 → 夹到上限 0.15
    expect(pickThresholdFromSize(5)).toBeCloseTo(0.1, 10);
  });

  it("小场景夹到下限，避免必须精确点线", () => {
    expect(pickThresholdFromSize(0.1)).toBe(0.005);
  });

  it("非法尺寸回落默认值", () => {
    expect(pickThresholdFromSize(NaN)).toBe(0.02);
    expect(pickThresholdFromSize(0)).toBe(0.02);
    expect(pickThresholdFromSize(-3)).toBe(0.02);
  });
});
