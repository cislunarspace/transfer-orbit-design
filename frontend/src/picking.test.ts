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

// —— 图例联动拾取（#460）：预览与聚焦正交的逐线不透明度 ——
// Legend-linked picking (#460): per-line opacity with preview orthogonal to focus.

import { lineOpacity } from "./picking";

describe("lineOpacity（#460）", () => {
  it("预览与聚焦皆空：全部原色", () => {
    expect(lineOpacity(0, null, null)).toBe(1);
    expect(lineOpacity(3, null, null)).toBe(1);
  });

  it("有聚焦：被指线原色，其余淡出", () => {
    expect(lineOpacity(1, 1, null)).toBe(1);
    expect(lineOpacity(0, 1, null)).toBe(0.15);
    expect(lineOpacity(2, 1, null)).toBe(0.15);
  });

  it("预览优先于聚焦：预览线原色，其余（含聚焦线）淡出", () => {
    expect(lineOpacity(2, 1, 2)).toBe(1);
    expect(lineOpacity(1, 1, 2)).toBe(0.15);
    expect(lineOpacity(0, 1, 2)).toBe(0.15);
  });

  it("预览为空回落聚焦视图", () => {
    expect(lineOpacity(1, 1, null)).toBe(1);
  });

  it("淡出度可传入（默认 0.15）", () => {
    expect(lineOpacity(0, 1, null, 0.3)).toBe(0.3);
    expect(lineOpacity(1, 1, null, 0.3)).toBe(1);
  });
});
