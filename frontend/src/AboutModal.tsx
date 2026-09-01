import React, { useEffect, useState } from "react";
import { Modal, Typography, Button, Space, message } from "antd";
import { DownloadOutlined, InfoCircleOutlined, SyncOutlined } from "@ant-design/icons";
import { openUrl } from "@tauri-apps/plugin-opener";
import { getVersion } from "@tauri-apps/api/app";
import { useTranslation } from "./i18n";
import {
  checkForAppUpdates,
  getBundleType,
  inAppUpdateSupported,
  RELEASES_PAGE_URL,
  type BundleType,
  type UpdateInfo,
} from "./updater";

const { Paragraph, Title } = Typography;

export interface AboutModalProps {
  open: boolean;
  onClose: () => void;
  onUpdateAvailable: (info: UpdateInfo) => void;
  /** 注入显示用的版本号（测试用）；缺省时取 Tauri 运行时真实版本 */
  /** Injected display version (for tests); falls back to the real Tauri runtime version. */
  currentVersion?: string;
}

export const AboutModal: React.FC<AboutModalProps> = ({
  open,
  onClose,
  onUpdateAvailable,
  currentVersion,
}) => {
  const { t } = useTranslation();
  const [checking, setChecking] = useState(false);
  const [runtimeVersion, setRuntimeVersion] = useState<string | null>(null);
  // 打包形态决定更新入口行为：deb/rpm 无应用内更新，按钮变为前往下载页
  // The bundle type decides the update entry: deb/rpm gets a download-page
  // link instead of the in-app updater.
  const [bundleType, setBundleType] = useState<BundleType>("unknown");

  useEffect(() => {
    if (currentVersion) return;
    getVersion()
      .then(setRuntimeVersion)
      .catch(() => setRuntimeVersion("unknown"));
  }, [currentVersion]);

  // 每次弹出时刷新（同一进程内不变，取失败回退 unknown 走 updater 原行为）
  // Refreshed on each open; stable within a process. On failure we fall back
  // to "unknown", which keeps the updater path.
  useEffect(() => {
    if (!open) return;
    getBundleType()
      .then(setBundleType)
      .catch(() => setBundleType("unknown"));
  }, [open]);

  const displayVersion = currentVersion ?? runtimeVersion ?? "…";

  const handleCheckUpdate = async () => {
    // deb/rpm 安装没有应用内更新通道：打开 Releases 页手动下载
    // deb/rpm installs have no in-app update channel: open the releases page.
    if (!inAppUpdateSupported(bundleType)) {
      try {
        await openUrl(RELEASES_PAGE_URL);
        message.info(t("updater.in_app_unsupported"));
      } catch (err: any) {
        message.error(`${t("updater.error")}: ${err?.message || String(err)}`);
      }
      return;
    }
    setChecking(true);
    try {
      const update = await checkForAppUpdates();
      if (update) {
        onClose();
        onUpdateAvailable(update);
      } else {
        message.info(t("updater.latest"));
      }
    } catch (err: any) {
      message.error(`${t("updater.error")}: ${err?.message || String(err)}`);
    } finally {
      setChecking(false);
    }
  };

  return (
    <Modal
      title={
        <Space>
          <InfoCircleOutlined />
          <span>关于 tod (Transfer Orbit Design)</span>
        </Space>
      }
      open={open}
      onCancel={onClose}
      footer={
        <Space>
          <Button
            icon={
              inAppUpdateSupported(bundleType) ? (
                <SyncOutlined spin={checking} />
              ) : (
                <DownloadOutlined />
              )
            }
            loading={checking}
            onClick={handleCheckUpdate}
          >
            {inAppUpdateSupported(bundleType)
              ? t("updater.check_action")
              : t("updater.manual_download_action")}
          </Button>
          <Button type="primary" onClick={onClose}>
            确定
          </Button>
        </Space>
      }
    >
      <div style={{ padding: "12px 0" }}>
        <Title level={4} style={{ margin: 0 }}>
          tod - 地月转移轨道设计系统
        </Title>
        <Paragraph type="secondary" style={{ marginTop: 4 }}>
          版本号：v{displayVersion}
        </Paragraph>
        <Paragraph>
          基于 CR3BP 高精度动力学模型与星历转换算法，支持平动点轨道生成、转移轨道设计及轨道保持仿真。
        </Paragraph>
      </div>
    </Modal>
  );
};
