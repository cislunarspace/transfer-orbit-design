// sidecar 族生成的前端封装：Tauri command 调用 + 类型。

export interface FamilyMember {
  states: number[]; // n×6 状态（初态帧时 n=1）
  times: number[];
  period: number | null;
}

export interface FamilyResponse {
  recordId: string;
  familyType: string;
  generatedMembers: number;
  mu: number | null;
  members: FamilyMember[];
  error: { code: string; message: string } | null;
}

export async function generateFamily(arguments_: Record<string, unknown>): Promise<FamilyResponse> {
  const { invoke } = await import("@tauri-apps/api/core");
  return invoke("generate_family", { arguments: arguments_ });
}

export interface ArtifactData {
  recordId: string;
  orbitFamily: string;
  memberCount: number;
  members: number[][]; // 每成员 n×3 xyz
  error: { code: string; message: string } | null;
}

export async function getArtifact(recordId: string): Promise<ArtifactData> {
  const { invoke } = await import("@tauri-apps/api/core");
  return invoke("get_artifact", { recordId });
}
