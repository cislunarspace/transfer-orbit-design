// 轨道库与工作流 API 封装（对应 ADR 0035 与 e2m2e 14 工具协议）
// Orbit-library and workflow API wrappers (ADR 0035; the e2m2e 14-tool protocol).

import { invoke } from "@tauri-apps/api/core";
import { ephemerisUtcToEt } from "./trajectoryParsing";
import { SECONDS_PER_DAY } from "./timeBasis";

export interface CatalogRecord {
  record_id: string;
  orbit_family: string;
  libration_point?: number;
  jacobi?: number;
  jacobi_min?: number;
  jacobi_max?: number;
  amplitude_km?: number;
  amplitude_min_km?: number;
  amplitude_max_km?: number;
  member_count?: number;
  has_cr3bp?: boolean;
  has_ephemeris?: boolean;
  /** 转移类型（HMN/LGA/WSB/low_thrust）；非 transfer 记录缺省（ADR 0042，#470） */
  transfer_type?: string | null;
  /** 分类学规范标签串（ADR 0042；未打标为 null），首个标签决定子分组 */
  taxonomy_labels?: string[] | null;
  source_tool?: string;
  source_record_id?: string;
  created_at?: string;
  tags?: string[];
  note?: string;
  [key: string]: unknown;
}

export interface CatalogQueryResponse {
  records: CatalogRecord[];
  message: string;
}

/** 保留标签值：出现即视为星标（星形切换 / 仅看星标过滤共用）。 */
/** The reserved tag value: its presence marks a starred record (shared by the star toggle / starred-only filter). */
export const STAR_TAG = "★";

// 分组判别的兜底 tool 映射（结构化字段不足时才用）；主口径是下面的结构化字段
// Fallback tool mapping for grouping (used only when structured fields are
// inconclusive); the primary rule reads the structured fields below.
const ARTIFACT_TYPE_BY_TOOL: Record<string, string> = {
  design_orbit: "orbit",
  catalog_promote: "orbit",
  orbit_family_generation: "family",
  control_orbit: "ephemeris",
};

/** catalog 记录 → 项目树分组的判别（#470 唯一事实的前端镜像；规范实现是后端
 *  src/engine/catalog_service.py::record_to_artifact，改动需两侧同步）：
 *  member_count > 1 → family；transfer_type 非空 → transfer；
 *  有星历段且无 CR3BP 段（纯星历记录）→ ephemeris；皆不命中回退 tool 映射，
 *  未知工具兜底 orbit。 */
/** Record -> tree-group classification (#470 frontend mirror of the single
 *  source of truth; the canonical implementation is the backend
 *  src/engine/catalog_service.py::record_to_artifact — keep both in sync):
 *  member_count > 1 -> family; non-empty transfer_type -> transfer; ephemeris
 *  segment without a CR3BP segment -> ephemeris; otherwise the tool mapping,
 *  with unknown tools defaulting to orbit. */
export function classifyArtifactType(r: CatalogRecord): string {
  if ((r.member_count ?? 0) > 1) return "family";
  if (r.transfer_type) return "transfer";
  if (Boolean(r.has_ephemeris) && !r.has_cr3bp) return "ephemeris";
  return ARTIFACT_TYPE_BY_TOOL[r.source_tool ?? ""] ?? "orbit";
}

// ADR 0042 一级类别判别：resonant 统一 resonant_ 前缀；moon_centered 仅 4 个
// 规范标签；其余规范标签皆共线平动点类（42 标签词汇表随 e2m2e 版本走，升级时核对）
// ADR 0042 top-category inference: resonant shares the resonant_ prefix;
// moon_centered is exactly these 4 canonical labels; every other canonical
// label is a collinear libration-point one (the 42-label vocabulary tracks
// the pinned e2m2e version — re-check on upgrades).
const MOON_CENTERED_LABELS = new Set([
  "distant_retrograde",
  "distant_prograde",
  "low_prograde_eastern",
  "low_prograde_western",
]);

export type TaxonomyCategory = "libration_point" | "moon_centered" | "resonant";

/** 记录 taxonomy 标签的一级类别（取首个标签；未打标返回 null → 「未分类」）。 */
/** The record's taxonomy top category (first label wins; null when unlabeled
 *  -> the "unclassified" subgroup). */
export function taxonomyCategoryOf(labels?: string[] | null): TaxonomyCategory | null {
  const first = labels?.[0];
  if (!first) return null;
  if (first.startsWith("resonant_")) return "resonant";
  return MOON_CENTERED_LABELS.has(first) ? "moon_centered" : "libration_point";
}

export async function catalogQuery(filters: Record<string, unknown>): Promise<CatalogQueryResponse> {
  return invoke<CatalogQueryResponse>("catalog_query", { arguments: filters });
}

export async function catalogTag(recordId: string, tags: string[], note?: string): Promise<boolean> {
  const resp = await invoke<{ status: string }>("run_tool", {
    tool: "catalog_tag",
    arguments: { record_id: recordId, tags, note },
    binaryDtype: null,
  });
  return resp.status === "ok";
}

export async function catalogPromote(recordId: string, memberIndex: number): Promise<string | null> {
  const resp = await invoke<{ data?: { record_id?: string }; status: string }>("run_tool", {
    tool: "catalog_promote",
    arguments: { record_id: recordId, member_index: memberIndex },
    binaryDtype: null,
  });
  return resp.data?.record_id ?? null;
}

export async function catalogExport(filters: Record<string, unknown>, dest: string): Promise<number> {
  const resp = await invoke<{ data?: { exported_count?: number }; status: string }>("run_tool", {
    tool: "catalog_export",
    arguments: { ...filters, dest },
    binaryDtype: null,
  });
  return resp.data?.exported_count ?? 0;
}

export async function catalogDelete(recordIds: string[]): Promise<boolean> {
  const resp = await invoke<{ status: string }>("run_tool", {
    tool: "catalog_delete",
    arguments: { record_ids: recordIds },
    binaryDtype: null,
  });
  return resp.status === "ok";
}

/** catalog_get 的帧通道结果：arrays 中值为 null 的占位键与 frames 按序一一
 *  对应（e2m2e ADR 0035；serde_json preserve_order 下键序在 Rust/JS 两侧
 *  均保持，Rust get_artifact 同款映射）。 */
/** catalog_get's frame-channel result: null-placeholder keys in arrays pair
 *  with frames in order (e2m2e ADR 0035; with serde_json preserve_order the
 *  key order survives into JS — the same mapping Rust's get_artifact uses). */
export interface CatalogGetResult {
  arrays: Record<string, unknown>;
  frames: { dtype: string; shape: number[]; data: number[] }[];
}

/** 取回一条库记录（catalog_get，#416：站保弹窗用真实星历跨弧做阻断判据）。
 *  星历段数组（eph/ 前缀）只随帧通道返回，dtype 必须 f64：JD_TDB 量级
 *  ~2.46e6 天，f32 尾数只剩 ~0.25 天精度。 */
/** Fetch one catalog record (catalog_get; #416: the station-keeping modal
 *  gates on the record's real ephemeris span). The eph/ arrays ride the frame
 *  channel only, and the dtype must be f64: at JD_TDB magnitudes (~2.46e6
 *  days) an f32 mantissa leaves only ~0.25-day precision. */
export async function catalogGet(recordId: string): Promise<CatalogGetResult> {
  const resp = await invoke<{
    data?: { arrays?: Record<string, unknown> };
    frames?: CatalogGetResult["frames"];
    error?: { code: string; message: string } | null;
  }>("run_tool", {
    tool: "catalog_get",
    arguments: { record_id: recordId },
    binaryDtype: "f64",
  });
  if (resp.error) {
    throw new Error(String(resp.error.message ?? resp.error.code));
  }
  return { arrays: resp.data?.arrays ?? {}, frames: resp.frames ?? [] };
}

/** e2m2e 记录存储的星历段键（data/catalog/record.py：EPHEMERIS_PREFIX = "eph"，
 *  时间数组为 UTC 分量 + 可选 JD_TDB，无独立的“天”数组）。 */
/** Ephemeris-segment keys in e2m2e's record storage (data/catalog/record.py:
 *  EPHEMERIS_PREFIX = "eph"; the time arrays are UTC components plus an
 *  optional JD_TDB — there is no standalone days array). */
const EPH_KEYS = {
  jd: "eph/times_jd_tdb",
  year: "eph/year",
  month: "eph/month",
  day: "eph/day",
  hour: "eph/hour",
  minute: "eph/minute",
  second: "eph/second",
} as const;

/** catalog_get 结果中星历段的覆盖弧长（天）：优先 eph/times_jd_tdb（JD，
 *  天），否则由 UTC 分量合成 et 秒取极差；无星历段或数据不齐返回 null。 */
/** The ephemeris segment's coverage span (days) from a catalog_get result:
 *  prefer eph/times_jd_tdb (JD, days), else compose et seconds from the UTC
 *  components; null when the segment is absent or incomplete. */
export function ephemerisSpanDays(res: CatalogGetResult): number | null {
  const nullKeys = Object.entries(res.arrays)
    .filter(([, v]) => v === null)
    .map(([k]) => k);
  const frameOf = (key: string): number[] | null => {
    const idx = nullKeys.indexOf(key);
    const data = idx >= 0 ? res.frames[idx]?.data : undefined;
    return Array.isArray(data) ? (data as number[]) : null;
  };

  const jd = frameOf(EPH_KEYS.jd);
  let times: number[];
  let unitDays: boolean;
  if (jd && jd.length > 1 && jd.every((v) => Number.isFinite(v))) {
    times = jd;
    unitDays = true;
  } else {
    const n = frameOf(EPH_KEYS.year)?.length ?? 0;
    const et = ephemerisUtcToEt(
      {
        year: frameOf(EPH_KEYS.year),
        month: frameOf(EPH_KEYS.month),
        day: frameOf(EPH_KEYS.day),
        hour: frameOf(EPH_KEYS.hour),
        minute: frameOf(EPH_KEYS.minute),
        second: frameOf(EPH_KEYS.second),
      },
      n,
    );
    if (!et) return null;
    times = et;
    unitDays = false;
  }
  const span = Math.max(...times) - Math.min(...times);
  return unitDays ? span : span / SECONDS_PER_DAY;
}
