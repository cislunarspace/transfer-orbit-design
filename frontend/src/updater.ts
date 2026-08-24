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

