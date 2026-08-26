// 项目与生成命令的前端封装。
// Frontend wrappers for the project and generation commands.

import type { ArtifactSummary } from "./projectTypes";

export type { ArtifactSummary };

export async function listArtifacts(): Promise<ArtifactSummary[]> {
  const { invoke } = await import("@tauri-apps/api/core");
  return invoke("list_artifacts");
}

export async function removeArtifact(artifactId: string): Promise<boolean> {
  const { invoke } = await import("@tauri-apps/api/core");
  return invoke("remove_artifact", { artifactId });
}