export interface ArtifactSummary {
  artifactId: string;
  artifactType: string;
  label: string;
  orbitType: string;
  sourceTool: string;
  recordId: string | null;
  createdAt: string;
  /** 星标与备注（catalog 查询路径带回；会话产物行缺省） */
  /** Star/note metadata (returned by the catalog-query path; absent on session-artifact rows). */
  tags?: string[];
  note?: string;
  /** 结构化摘要富化字段（catalog 查询路径带回；会话产物行缺省）——
   *  树行第二行与轨道保持入口判断消费 */
  /** Structured summary enrichment (returned by the catalog-query path;
   *  absent on session-artifact rows) — feeds the tree row's second line
   *  and the station-keeping entry check. */
  librationPoint?: number;
  jacobi?: number;
  memberCount?: number;
  hasEphemeris?: boolean;
}