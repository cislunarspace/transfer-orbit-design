// 情景（scenario）v1（#429，grilling 2026-08-30 定稿）：固定层记录集 +
// 参考历元 + 播放配置的序列化格式与解析。情景是对外文件契约（未来的
// 助手链路与平行世界回放都以它为底座），版本演进只增不改；未知版本拒绝
// 加载并提示，不静默。
// Scenario v1 (#429, finalized by the 2026-08-30 grilling): the pinned-layer
// record set + reference epoch + playback config, serialized and parsed. A
// scenario is an outward file contract (future assistant wiring and
// parallel-world replay build on it); versions only append, never rewrite —
// an unknown version is refused with a clear message, never silently.

import { etFromEpoch } from "./timeBasis";

/** 文件格式标识与版本（顶层 format/version 字段）。 */
/** The file format tag and version (top-level format/version fields). */
export const SCENARIO_FORMAT = "tod-scenario";
export const SCENARIO_VERSION = 1;

/** 播放配置：rate = 物理秒/真实秒（TimelineBar 播放步长倍率）；loop =
 *  循环；startOffsetEt = 播放/校准起点相对参考历元的偏移（et 秒，v1
 *  保存端恒写 0，字段供外部情景与后续版本使用）。 */
/** Playback config: rate = physical seconds per wall second (the TimelineBar
 *  playback step multiplier); loop = looping; startOffsetEt = the offset of
 *  the playback/calibration start from the reference epoch (et seconds; the
 *  v1 saver always writes 0 — the field serves external scenarios and later
 *  versions). */
export interface ScenarioPlayback {
  rate: number;
  loop: boolean;
  startOffsetEt: number;
}

export const DEFAULT_PLAYBACK: ScenarioPlayback = { rate: 86400, loop: true, startOffsetEt: 0 };

/** 情景正文三块：记录引用列表（catalog record_id）、参考历元（et 秒或
 *  UTC 二选一表示；et 是唯一绝对基准，ADR 0021 修订，序列化恒写 et）、
 *  播放配置。 */
/** The scenario body's three blocks: the record reference list (catalog
 *  record_ids), the reference epoch (either et seconds or UTC; et is the only
 *  absolute basis per the ADR 0021 revision — serialization always writes et),
 *  and the playback config. */
export interface ScenarioContent {
  records: string[];
  referenceEpoch: { et: number } | { utc: string };
  playback: ScenarioPlayback;
}

/** 解析后的情景：参考历元统一到 et 秒。 */
/** The parsed scenario: the reference epoch unified into et seconds. */
export interface ResolvedScenario {
  records: string[];
  referenceEt: number;
  playback: ScenarioPlayback;
}

export function serializeScenario(s: ScenarioContent): string {
  return JSON.stringify(
    { format: SCENARIO_FORMAT, version: SCENARIO_VERSION, ...s },
    null,
    2,
  );
}

export type ParsedScenario =
  | { scenario: ResolvedScenario }
  | { error: string };

/** 解析情景文本：块级严格（records/referenceEpoch/playback 三块必须齐）、
 *  字段级宽容（playback 内字段缺省取默认值）。坏文件明确报错，不静默。 */
/** Parses scenario text: block-strict (the records/referenceEpoch/playback
 *  blocks are all required), field-lenient (missing playback fields fall back
 *  to defaults). A malformed file errors explicitly, never silently. */
export function parseScenario(text: string): ParsedScenario {
  let raw: unknown;
  try {
    raw = JSON.parse(text);
  } catch {
    return { error: "情景文件不是合法 JSON" };
  }
  const obj = raw as Record<string, unknown> | null;
  if (!obj || typeof obj !== "object" || Array.isArray(obj)) {
    return { error: "情景文件结构不合法" };
  }
  if (obj.format !== SCENARIO_FORMAT) {
    return { error: `不是情景文件（format 应为 ${SCENARIO_FORMAT}）` };
  }
  if (obj.version !== SCENARIO_VERSION) {
    return { error: `未知情景版本 ${String(obj.version)}（当前支持版本 ${SCENARIO_VERSION}），请升级应用后再打开` };
  }
  if (!Array.isArray(obj.records) || !obj.records.every((r) => typeof r === "string")) {
    return { error: "情景的 records 应为记录 id 字符串数组" };
  }
  const epoch = obj.referenceEpoch as { et?: unknown; utc?: unknown } | undefined;
  if (!epoch || typeof epoch !== "object" || Array.isArray(epoch)) {
    return { error: "情景缺少参考历元（referenceEpoch）" };
  }
  let referenceEt: number;
  if (typeof epoch.et === "number" && Number.isFinite(epoch.et)) {
    referenceEt = epoch.et;
  } else if (typeof epoch.utc === "string") {
    referenceEt = etFromEpoch(epoch.utc);
    if (!Number.isFinite(referenceEt)) {
      return { error: `情景参考历元 UTC 无法解析：${epoch.utc}` };
    }
  } else {
    return { error: "情景参考历元需要 et（秒）或 utc（ISO 字符串）二选一" };
  }
  const pb = obj.playback as Record<string, unknown> | undefined;
  if (!pb || typeof pb !== "object" || Array.isArray(pb)) {
    return { error: "情景缺少播放配置（playback）" };
  }
  const rate = pb.rate;
  const loop = pb.loop;
  const offset = pb.startOffsetEt;
  if (rate !== undefined && !(typeof rate === "number" && Number.isFinite(rate) && rate > 0)) {
    return { error: "情景播放速率（rate）应为正数（物理秒/真实秒）" };
  }
  if (loop !== undefined && typeof loop !== "boolean") {
    return { error: "情景循环开关（loop）应为布尔值" };
  }
  if (offset !== undefined && !(typeof offset === "number" && Number.isFinite(offset))) {
    return { error: "情景播放起点偏移（startOffsetEt）应为有限数（et 秒）" };
  }
  return {
    scenario: {
      records: obj.records as string[],
      referenceEt,
      playback: {
        rate: (rate as number) ?? DEFAULT_PLAYBACK.rate,
        loop: (loop as boolean) ?? DEFAULT_PLAYBACK.loop,
        startOffsetEt: (offset as number) ?? DEFAULT_PLAYBACK.startOffsetEt,
      },
    },
  };
}

/** 固定层条目的解析结果形状由调用方给出（App 的 PinnedRecord），
 *  resolveScenarioRecords 以泛型承载，scenario 不反向依赖 App。 */
/** The resolved pinned-entry shape comes from the caller (App's
 *  PinnedRecord): resolveScenarioRecords carries it generically so scenario
 *  never depends back on App. */

export interface ScenarioRecordResolution<T> {
  resolved: T[];
  /** 解析失败（已删除/读取失败/无轨迹）被跳过的记录 id */
  /** Record ids skipped as unresolvable (deleted / unreadable / trackless) */
  missing: string[];
  /** 引用数超过固定层上限，截断到上限（未尝试的 id 不进 missing） */
  /** References beyond the pinned-layer cap, truncated to it (untried ids stay out of missing) */
  truncated: boolean;
}

/** 逐 record_id 解析固定层条目：fetchRecord 返回 null 或抛错都按缺失跳过
 *  （沿仓库软失败先例——列出缺失项后加载其余）；达到上限即截断并停止
 *  后续取数。 */
/** Resolves pinned-layer entries record-id by record-id: a null or throwing
 *  fetchRecord counts as missing and is skipped (the repo's soft-failure
 *  precedent — list the missing, load the rest); hitting the cap truncates
 *  and stops further fetches. */
export async function resolveScenarioRecords<T>(
  recordIds: string[],
  limit: number,
  fetchRecord: (recordId: string) => Promise<T | null>,
): Promise<ScenarioRecordResolution<T>> {
  const resolved: T[] = [];
  const missing: string[] = [];
  let truncated = false;
  for (const id of recordIds) {
    if (resolved.length >= limit) {
      truncated = true;
      break;
    }
    try {
      const item = await fetchRecord(id);
      if (item === null) missing.push(id);
      else resolved.push(item);
    } catch {
      missing.push(id);
    }
  }
  return { resolved, missing, truncated };
}
