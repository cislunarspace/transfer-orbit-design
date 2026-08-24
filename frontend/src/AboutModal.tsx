import React, { useState } from "react";
import { Modal, Typography, Button, Space, message } from "antd";
import { InfoCircleOutlined, SyncOutlined } from "@ant-design/icons";
import { useTranslation } from "./i18n";
import { checkForAppUpdates, type UpdateInfo } from "./updater";

const { Paragraph, Title } = Typography;

export interface AboutModalProps {
  open: boolean;
  onClose: () => void;
  onUpdateAvailable: (info: UpdateInfo) => void;
  currentVersion?: string;
}

export const AboutModal: React.FC<AboutModalProps> = ({
  open,
  onClose,
  onUpdateAvailable,
  currentVersion = "4.1.2",
}) => {
  const { t } = useTranslation();
  const [checking, setChecking] = useState(false);

  const handleCheckUpdate = async () => {
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
            icon={<SyncOutlined spin={checking} />}
            loading={checking}
            onClick={handleCheckUpdate}
          >
            {t("updater.check_action")}
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
          版本号：v{currentVersion}
        </Paragraph>
        <Paragraph>
          基于 CR3BP 高精度动力学模型与星历转换算法，支持平动点轨道生成、转移轨道设计及轨道保持仿真。
        </Paragraph>
      </div>
    </Modal>
  );
};
