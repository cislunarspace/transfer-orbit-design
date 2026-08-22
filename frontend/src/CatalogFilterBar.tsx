// 轨道库过滤栏：catalog_query 参数 → ParamsPanel 复用 → 查询结果入项目树。

import { useEffect, useState } from "react";
import { ParamsPanel } from "./ParamsPanel";
import type { ToolSchema } from "./schema";
import catalogQuerySchema from "./toolSchemas/catalog_query.json";
import type { ArtifactSummary } from "./projectApi";

export interface CatalogFilterBarProps {
  onResults: (artifacts: ArtifactSummary[], count: number, message: string) => void;
}

export async function queryCatalog(
  filters: Record<string, unknown>,
): Promise<{ records: unknown[]; message: string }> {
  const { invoke } = await import("@tauri-apps/api/core");
  return invoke("catalog_query", { arguments: filters });
}

export function CatalogFilterBar({ onResults }: CatalogFilterBarProps) {
  const [params, setParams] = useState<Record<string, unknown>>({});
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    // 初次加载全库（空过滤）
    onQuery({});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const onQuery = async (p: Record<string, unknown>) => {
    setBusy(true);
    try {
      const cleaned = Object.fromEntries(
        Object.entries(p).filter(([, v]) => v !== null && v !== undefined && v !== ""),
      );
      const resp = await queryCatalog(cleaned);
      onResults(
        (resp.records as Record<string, unknown>[]).map((r) => ({
          artifactId: String(r.record_id ?? ""),
          artifactType: r.source_tool === "orbit_family_generation" ? "family" : "orbit",
          label: `${String(r.orbit_family ?? "")}（${r.member_count ?? 0} 成员）`,
          orbitType: String(r.orbit_family ?? ""),
          sourceTool: String(r.source_tool ?? ""),
          recordId: (r.record_id as string) ?? null,
          createdAt: String(r.created_at ?? ""),
        })),
        resp.records.length,
        resp.message,
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <ParamsPanel
        schema={catalogQuerySchema as unknown as ToolSchema}
        params={params}
        onParamsChange={setParams}
      />
      <button onClick={() => onQuery(params)} disabled={busy} style={{ width: "100%", marginTop: 8 }}>
        {busy ? "查询中…" : "查询"}
      </button>
    </div>
  );
}
