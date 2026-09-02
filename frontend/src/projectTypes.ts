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
  /** taxonomy 规范标签串（catalog 查询路径带回；会话产物行缺省）——
   *  轨道/轨道族组的一级类别子分组依据（#470），缺省不参与分层 */
  /** Canonical taxonomy labels (returned by the catalog-query path; absent on
   *  session-artifact rows) — drives the top-category subgrouping inside the
   *  orbit/family groups (#470); rows without labels stay ungrouped. */
  taxonomyLabels?: string[] | null;
}