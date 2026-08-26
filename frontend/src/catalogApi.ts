// 轨道库与工作流 API 封装（对应 ADR 0035 与 e2m2e 14 工具协议）
// Orbit-library and workflow API wrappers (ADR 0035; the e2m2e 14-tool protocol).

import { invoke } from "@tauri-apps/api/core";

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

export async function computeStability(recordId: string): Promise<Record<string, unknown>> {
  const resp = await invoke<{ data: Record<string, unknown>; status: string }>("run_tool", {
    tool: "orbit_stability",
    arguments: { orbit: recordId },
    binaryDtype: null,
  });
  return resp.data;
}
