import { check, type Update } from "@tauri-apps/plugin-updater";

export interface UpdateInfo {
  version: string;
  currentVersion: string;
  body?: string;
  rawUpdate: Update;
}

export type UpdateStatus =
  | "idle"
  | "checking"
  | "available"
  | "up-to-date"
  | "downloading"
  | "downloaded"
  | "error";

export async function checkForAppUpdates(
  checkFn: () => Promise<Update | null> = check
): Promise<UpdateInfo | null> {
  const update = await checkFn();
  if (!update) {
    return null;
  }
  return {
    version: update.version,
    currentVersion: update.currentVersion,
    body: update.body,
    rawUpdate: update,
  };
}

export type DownloadEvent =
  | { event: "Started"; data: { contentLength?: number } }
  | { event: "Progress"; data: { chunkLength: number } }
  | { event: "Finished" };

export async function downloadAndApplyUpdate(
  updateInfo: UpdateInfo,
  onEvent?: (event: DownloadEvent) => void
): Promise<void> {
  await updateInfo.rawUpdate.downloadAndInstall((event) => {
    if (onEvent) {
      onEvent(event as DownloadEvent);
    }
  });
}

/** 字节数转人类可读（B 取整，KB 以上一位小数） */
export function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  let value = bytes;
  let i = 0;
  while (value >= 1024 && i < units.length - 1) {
    value /= 1024;
    i += 1;
  }
  return i === 0 ? `${Math.round(value)} B` : `${value.toFixed(1)} ${units[i]}`;
}

/** 下载速度跟踪：指数移动平均平滑瞬时速率，避免 UI 跳变。
 *  返回 B/s；首个分块无时间差，返回 0。 */
export function createSpeedTracker(): (nowMs: number, chunkBytes: number) => number {
  let lastMs: number | null = null;
  let smoothed = 0;
  return (nowMs, chunkBytes) => {
    if (lastMs !== null) {
      const dt = (nowMs - lastMs) / 1000;
      if (dt > 0) {
        const instant = chunkBytes / dt;
        smoothed = smoothed === 0 ? instant : smoothed * 0.7 + instant * 0.3;
      }
    }
    lastMs = nowMs;
    return smoothed;
  };
}

