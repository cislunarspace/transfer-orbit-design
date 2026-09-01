import { invoke } from "@tauri-apps/api/core";
import { check, type Update } from "@tauri-apps/plugin-updater";

/** GitHub Releases 页（latest 自动重定向到最新 tag），deb/rpm 安装的手动更新入口。 */
/** GitHub Releases page (latest redirects to the newest tag): manual update
 *  entry for deb/rpm installs. */
export const RELEASES_PAGE_URL =
  "https://github.com/cislunarspace/transfer-orbit-design/releases/latest";

export type BundleType =
  | "appimage"
  | "deb"
  | "rpm"
  | "nsis"
  | "msi"
  | "app"
  | "unknown";

/** 打包形态由 tauri-build 构建期二进制补丁决定；开发态（未打包）返回 null → "unknown"。 */
/** The bundle type is binary-patched at build time by tauri-build; dev builds
 *  (unpackaged) report null → "unknown". */
export async function getBundleType(): Promise<BundleType> {
  const t = await invoke<string | null>("bundle_type");
  return (t ?? "unknown") as BundleType;
}

/** 应用内更新仅在 AppImage 与 Windows/macOS 安装器下可用。deb/rpm 不在列：
 *  更新清单平台键（linux-{arch}）无安装格式维度，产物只有 AppImage，
 *  updater 在 deb/rpm 运行时按自身格式验型必败，只能引导手动下载。 */
/** In-app updates work for AppImage and the Windows/macOS installers only.
 *  deb/rpm are excluded: the manifest platform keys carry no bundle-format
 *  dimension and the Linux artifact is an AppImage, so the updater's format
 *  check fails on deb/rpm installs — manual download is the only path. */
export function inAppUpdateSupported(t: BundleType): boolean {
  return t !== "deb" && t !== "rpm";
}

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

