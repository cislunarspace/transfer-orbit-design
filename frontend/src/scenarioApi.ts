// 情景文件的前端封装（#429）：dialog 插件取路径 + Tauri 命令对落盘/读取。
// 对话框取消（返回 null）静默返回 false/null，不打扰用户。
// The frontend scenario wrapper (#429): the dialog plugin picks the path,
// the Tauri command pair writes/reads it. A cancelled dialog (null path)
// quietly returns false/null — never disturbs the user.

import { open, save } from "@tauri-apps/plugin-dialog";

/** 保存情景：另存为对话框 → save_scenario 命令写盘；取消返回 false。 */
/** Saves a scenario: save-as dialog → the save_scenario command; false when cancelled. */
export async function saveScenarioFile(content: string): Promise<boolean> {
  const { invoke } = await import("@tauri-apps/api/core");
  const path = await save({
    title: "保存情景",
    defaultPath: "scenario.json",
    filters: [{ name: "情景文件", extensions: ["json"] }],
  });
  if (!path) return false;
  await invoke("save_scenario", { path, content });
  return true;
}

/** 打开情景：选择文件对话框 → open_scenario 命令读文本；取消返回 null。
 *  对话框默认定位情景固定目录（ADR 0027，scenarios_dir 命令；目录未建
 *  时回退无默认）。 */
/** Opens a scenario: open dialog → the open_scenario command returns the text;
 *  null when cancelled. The dialog defaults into the fixed scenarios dir
 *  (ADR 0027, the scenarios_dir command; no default when it doesn't exist
 *  yet). */
export async function openScenarioFile(): Promise<string | null> {
  const { invoke } = await import("@tauri-apps/api/core");
  let defaultPath: string | undefined;
  try {
    defaultPath = (await invoke<string | null>("scenarios_dir")) ?? undefined;
  } catch {
    // 目录命令不可用（旧二进制/目录未建）：无默认定位，不影响选择
    // Directory command unavailable (older binary / dir not yet created): no
    // default location, selection still works.
  }
  const path = await open({
    title: "打开情景",
    multiple: false,
    directory: false,
    filters: [{ name: "情景文件", extensions: ["json"] }],
    defaultPath,
  });
  if (!path) return null;
  return invoke<string>("open_scenario", { path });
}
