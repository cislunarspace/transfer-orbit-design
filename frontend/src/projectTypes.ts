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
}