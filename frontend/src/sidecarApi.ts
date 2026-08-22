// sidecar 族生成的前端封装：Tauri command 调用 + 类型。

export interface FamilyMember {
  positions: number[]; // 一维 xyz（当前每成员仅初态，#525 落地后为整条轨迹）
  pointCount: number;
  times: number[];
}

export interface FamilyResponse {
  recordId: string;
  familyType: string;
  generatedMembers: number;
  members: FamilyMember[];
  error: { code: string; message: string } | null;
}

export async function generateFamily(arguments_: Record<string, unknown>): Promise<FamilyResponse> {
  const { invoke } = await import("@tauri-apps/api/core");
  return invoke("generate_family", { arguments: arguments_ });
}
