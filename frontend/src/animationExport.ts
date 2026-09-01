// 时间轴播放导出（#455）的纯判定逻辑：时刻扫描序列生成。
// Pure logic for timeline-playback export (#455): moment sweep-sequence
// generation.

/** 扫描 tick（毫秒）：与录制帧率解耦，只决定时刻推进密度。 */
/** The sweep tick (ms): decoupled from the recording frame rate — it only
 *  decides how densely the moment advances. */
export const SWEEP_TICK_MS = 50;

/** 时刻扫描序列：总步数 = 时长 × 1000 ÷ tick（至少 2 步，保证有起终两点），
 *  从量程起点匀速插值到终点。单点/倒挂/非法量程退化为空——调用方据此
 *  跳过扫描。 */
/** The moment sweep sequence: total steps = duration × 1000 ÷ tick (at least
 *  2 so both endpoints exist), interpolated evenly from the range start to
 *  its end. A single-point, inverted, or invalid range degenerates to empty —
 *  callers skip the sweep then. */
export function sweepMoments(
  range: [number, number],
  durationSec: number,
  tickMs: number = SWEEP_TICK_MS,
): number[] {
  const [lo, hi] = range;
  if (!Number.isFinite(lo) || !Number.isFinite(hi) || hi <= lo) return [];
  const steps = Math.max(2, Math.round((durationSec * 1000) / tickMs));
  const seq: number[] = [];
  for (let i = 0; i < steps; i++) {
    seq.push(lo + ((hi - lo) * i) / (steps - 1));
  }
  return seq;
}
