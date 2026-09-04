export interface ArtifactSummary {
  artifactId: string;
  artifactType: string;
  label: string;
  orbitType: string;
  sourceTool: string;
  recordId: string | null;
  createdAt: string;
  /** 星标与备注（catalog 查询路径带回；会话产物行缺省） */
  tags?: string[];
  note?: string;
  /** 结构化摘要富化字段（catalog 查询路径带回；会话产物行缺省）——
   *  树行第二行与轨道保持入口判断消费 */
  librationPoint?: number;
  jacobi?: number;
  /** 族内成员序号（e2m2e 5.9.3 一轨一记录；非族成员记录缺省） */
  memberIndex?: number;
  hasEphemeris?: boolean;
}
