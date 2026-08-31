import React, { useState } from "react";
import { Modal, Progress, Typography, Button, Space } from "antd";
import type { UpdateInfo } from "./updater";
import { downloadAndApplyUpdate, formatBytes, createSpeedTracker } from "./updater";
import { useTranslation } from "./i18n";

const { Text, Paragraph } = Typography;

export interface UpdateModalProps {
  updateInfo: UpdateInfo | null;
  open: boolean;
  onClose: () => void;
  onRestart?: () => void | Promise<void>;
}

export const UpdateModal: React.FC<UpdateModalProps> = ({
  updateInfo,
  open,
  onClose,
  onRestart,
}) => {
  const { t } = useTranslation();
  const [downloading, setDownloading] = useState(false);
  const [downloaded, setDownloaded] = useState(false);
  const [percent, setPercent] = useState<number>(0);
  const [totalBytes, setTotalBytes] = useState<number>(0);
  const [receivedBytes, setReceivedBytes] = useState<number>(0);
  const [speedBps, setSpeedBps] = useState<number>(0);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  if (!updateInfo) return null;

  const handleStartDownload = async () => {
    setDownloading(true);
    setErrorMsg(null);
    let totalLength = 0;
    let downloadedLength = 0;
    const tracker = createSpeedTracker();

    try {
      await downloadAndApplyUpdate(updateInfo, (evt) => {
        if (evt.event === "Started") {
          totalLength = evt.data.contentLength || 0;
          setTotalBytes(totalLength);
          setReceivedBytes(0);
          setSpeedBps(0);
          setPercent(0);
        } else if (evt.event === "Progress") {
          downloadedLength += evt.data.chunkLength;
          setReceivedBytes(downloadedLength);
          setSpeedBps(tracker(Date.now(), evt.data.chunkLength));
          if (totalLength > 0) {
            setPercent(Math.min(100, Math.round((downloadedLength / totalLength) * 100)));
          }
        } else if (evt.event === "Finished") {
          setPercent(100);
        }
      });
      setDownloading(false);
      setDownloaded(true);
    } catch (err: any) {
      setDownloading(false);
      setErrorMsg(err?.message || String(err));
    }
  };

  const handleRestart = async () => {
    if (onRestart) {
      await onRestart();
      return;
    }
    // 默认触发 Tauri relaunch
    // Falls back to a Tauri relaunch.
    try {
      const { relaunch } = await import("@tauri-apps/plugin-process");
      await relaunch();
    } catch {
      window.location.reload();
    }
  };

  return (
    <Modal
      title={
        downloaded
          ? t("updater.downloaded_title")
          : `${t("updater.available_title")} (v${updateInfo.version})`
      }
      open={open}
      onCancel={downloading ? undefined : onClose}
      footer={
        downloaded ? (
          <Button type="primary" onClick={handleRestart}>
            {t("updater.restart_now")}
          </Button>
        ) : (
          <Space>
            <Button disabled={downloading} onClick={onClose}>
              {t("updater.later")}
            </Button>
            <Button
              type="primary"
              loading={downloading}
              onClick={handleStartDownload}
            >
              {t("updater.download_now")}
            </Button>
          </Space>
        )
      }
      closable={!downloading}
      maskClosable={!downloading}
    >
      <div style={{ marginTop: 12 }}>
        {!downloaded ? (
          <>
            <Paragraph>
              {t("updater.available_desc").replace("{version}", updateInfo.version)}
            </Paragraph>
            {updateInfo.body && (
              <div
                style={{
                  maxHeight: 180,
                  overflowY: "auto",
                  background: "rgba(0,0,0,0.03)",
                  padding: 8,
                  borderRadius: 2,
                  marginBottom: 12,
                  whiteSpace: "pre-wrap",
                }}
              >
                <Text type="secondary">{updateInfo.body}</Text>
              </div>
            )}
            {downloading && (
              <div style={{ marginTop: 16 }}>
                <Text>{t("updater.downloading")}</Text>
                <Progress percent={percent} status={errorMsg ? "exception" : "active"} />
                <Text type="secondary">
                  {totalBytes > 0
                    ? t("updater.download_stats")
                        .replace("{received}", formatBytes(receivedBytes))
                        .replace("{total}", formatBytes(totalBytes))
                        .replace("{speed}", speedBps > 0 ? formatBytes(speedBps) : "—")
                    : t("updater.download_stats_no_total")
                        .replace("{received}", formatBytes(receivedBytes))
                        .replace("{speed}", speedBps > 0 ? formatBytes(speedBps) : "—")}
                </Text>
              </div>
            )}
            {errorMsg && (
              <div style={{ marginTop: 8 }}>
                <Text type="danger">{`${t("updater.error")}: ${errorMsg}`}</Text>
              </div>
            )}
          </>
        ) : (
          <Paragraph>{t("updater.downloaded_desc")}</Paragraph>
        )}
      </div>
    </Modal>
  );
};
