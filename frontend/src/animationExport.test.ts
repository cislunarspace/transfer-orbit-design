// 时刻扫描序列单测（#455）：时间轴播放导出把时刻从量程起点匀速扫到终点。
// 序列含起点与终点，步数 = 时长 ÷ tick；单点/无效量程退化为空。
// Sweep-sequence unit tests (#455): timeline-playback export sweeps the moment
// from the range start to its end at a fixed tick. The sequence includes both
// endpoints; a single-point or invalid range degenerates to empty.

import { describe, it, expect } from "vitest";
import { sweepMoments, SWEEP_TICK_MS } from "./animationExport";

describe("sweepMoments（#455）", () => {
  it("8 秒扫描：160 步，首尾分别是量程起终点", () => {
    const seq = sweepMoments([0, 8_000_000], 8);
    expect(seq).toHaveLength(160);
    expect(seq[0]).toBe(0);
    expect(seq[seq.length - 1]).toBe(8_000_000);
  });

  it("中间步均匀插值（等差）", () => {
    const seq = sweepMoments([100, 200], 2); // 40 步，步距 100/39
    const step = (seq[1] - seq[0]);
    for (let i = 1; i < seq.length; i++) {
      expect(seq[i] - seq[i - 1]).toBeCloseTo(step, 6);
    }
  });

  it("偏移量程：序列值落在量程内（起点非 0）", () => {
    const seq = sweepMoments([1_000_000, 1_100_000], 2);
    expect(seq[0]).toBe(1_000_000);
    expect(seq[seq.length - 1]).toBe(1_100_000);
  });

  it("单点/倒挂/非法量程退化为空", () => {
    expect(sweepMoments([5, 5], 8)).toEqual([]);
    expect(sweepMoments([10, 0], 8)).toEqual([]);
    expect(sweepMoments([0, NaN], 8)).toEqual([]);
  });

  it("步数至少 2（最短时长也有起终两点）", () => {
    const seq = sweepMoments([0, 1000], 0.01);
    expect(seq.length).toBeGreaterThanOrEqual(2);
    expect(SWEEP_TICK_MS).toBe(50);
  });
});
