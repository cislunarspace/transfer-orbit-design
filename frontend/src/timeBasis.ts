// 时间基准工具：et 秒（J2000 起算，TDB 口径）与历元/JD/UTC 的相互换算。
// ADR 0021 修订（2026-08-30）：et 秒是时间轴唯一绝对基准；本模块是前端
// 唯一的历元换算出口。
// Time-basis utilities: et seconds (seconds since J2000, TDB convention) and
// conversions to/from epochs, Julian dates, and UTC labels. Per the ADR 0021
// revision (2026-08-30), et seconds are the timeline's only absolute basis;
// this module is the frontend's single conversion exit.

/** J2000.0 的 JD（TDB≈TT 口径） */
/** JD of J2000.0 (TDB≈TT convention). */
export const JD_J2000 = 2451545.0;

/** JD of Unix epoch 1970-01-01 00:00 UTC */
export const JD_UNIX_EPOCH = 2440587.5;

/** 秒/天 */
/** Seconds per day. */
export const SECONDS_PER_DAY = 86400.0;

/**
 * 历元 → et 秒。接受 ISO UTC 字符串或 JD_TDB 浮点数（对齐 e2m2e
 * TransferDesignRequest.tli_epoch 的两种形态）。
 * Epoch → et seconds. Accepts an ISO UTC string or a JD_TDB float (matching
 * the two forms of e2m2e's TransferDesignRequest.tli_epoch).
 *
 * 精度说明：UTC→et 忽略 ~69 s 的 (TT−TAI)+TDB−UTC 偏差（2026 年为
 * 32.184 s + 37 闰秒），仅用于画布走查显示，不用于数值计算。
 * Precision note: the ~69 s (TT−TAI)+(TDB−UTC) offset is ignored — good for
 * canvas walkthrough display only, never for numerics.
 */
export function etFromEpoch(epoch: string | number): number {
  if (typeof epoch === "number") {
    if (!Number.isFinite(epoch)) return NaN;
    return (epoch - JD_J2000) * SECONDS_PER_DAY;
  }
  // e2m2e 的历元字符串是 UTC。无时区后缀的 date-time 形式会被
  // Date.parse 按本地时区解析——显式补 "Z" 强制 UTC（date-only 形式
  // 规范本就按 UTC，原样解析）。
  // e2m2e epoch strings are UTC. Offset-less date-time forms would parse as
  // LOCAL time — append "Z" to force UTC (date-only forms are already UTC
  // per spec, parse as-is).
  let iso = epoch.trim();
  if (!/^\d{4}-\d{2}-\d{2}$/.test(iso) && !/(?:Z|z|[+-]\d{2}:?\d{2})$/.test(iso)) {
    iso += "Z";
  }
  const ms = Date.parse(iso);
  if (!Number.isFinite(ms)) return NaN;
  const jd = ms / (SECONDS_PER_DAY * 1000) + JD_UNIX_EPOCH;
  return (jd - JD_J2000) * SECONDS_PER_DAY;
}

/** JD_TDB → et 秒 */
/** JD_TDB → et seconds. */
export function etFromJdTdb(jdTdb: number): number {
  return (jdTdb - JD_J2000) * SECONDS_PER_DAY;
}

/** et 秒 → JD（显示口径） */
/** et seconds → Julian date (display convention). */
export function etToJd(et: number): number {
  return et / SECONDS_PER_DAY + JD_J2000;
}

/** et 秒 → "YYYY-MM-DD HH:MM:SS"（UTC 显示口径，同上精度说明） */
/** et seconds → "YYYY-MM-DD HH:MM:SS" (UTC display label, same precision note). */
export function etToUtcLabel(et: number): string {
  if (!Number.isFinite(et)) return "—";
  const ms = (etToJd(et) - JD_UNIX_EPOCH) * SECONDS_PER_DAY * 1000;
  const d = new Date(ms);
  const p = (n: number, w = 2) => String(n).padStart(w, "0");
  return (
    `${d.getUTCFullYear()}-${p(d.getUTCMonth() + 1)}-${p(d.getUTCDate())} ` +
    `${p(d.getUTCHours())}:${p(d.getUTCMinutes())}:${p(d.getUTCSeconds())}`
  );
}
