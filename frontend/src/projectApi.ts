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

// AI 助手经 MCP 运行的产物登记入口（ADR 0022：AI 产物与手动运行语义一致，
// 同一项目树）。MCP 链路不过 run_tool，由工具卡片事件带回 record_id 登记。
// Registration entry for artifacts the AI assistant produces over MCP (ADR
// 0022: AI artifacts share the manual-run semantics, same project tree). The
// MCP link doesn't go through run_tool, so the record_id comes back via the
// tool-card event for registration here.
export async function registerArtifact(meta: {
  artifactType: string;
  label: string;
  orbitType?: string;
  sourceTool: string;
  recordId: string;
}): Promise<ArtifactSummary> {
  const { invoke } = await import("@tauri-apps/api/core");
  return invoke("register_artifact", meta);
}