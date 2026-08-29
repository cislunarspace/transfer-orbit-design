// 模型服务配置表单（CONTEXT.md 术语：模型服务）：OpenAI 兼容协议的
// baseUrl / 模型名 / API key，BYOK。嵌入设置弹窗的"AI 助手"分区，也是
// 边栏空态"去设置"的落点。API key 只在保存时经 IPC 写入后端 keyring，
// 不回读、不进 webview 持久层（ADR 0023 决策 6）。
// Model-service config form (CONTEXT.md term: model service): baseUrl / model
// name / API key over the OpenAI-compatible protocol, BYOK. Embedded in the
// settings modal's "AI Assistant" section and the target of the sidebar empty
// state's "go to settings". The API key is written to the backend keyring via
// IPC only on save — never read back, never persisted in the webview (ADR 0023,
// decision 6).

import { useEffect, useState } from "react";
import { Button, Form, Input, Select, Typography, message } from "antd";
import { assistantGetState, assistantSetConfig, assistantTestConfig } from "./api";
import { useTranslation } from "../i18n";

const { Text } = Typography;

// OpenAI 兼容协议的常见服务端点预设（ADR 0022 决策 5：一套协议覆盖云端与本地）
// Presets of common OpenAI-compatible endpoints (ADR 0022 decision 5: one
// protocol covers both cloud and local).
const PROVIDER_PRESETS: { label: string; baseUrl: string }[] = [
  { label: "DeepSeek", baseUrl: "https://api.deepseek.com" },
  { label: "通义千问 (DashScope 兼容)", baseUrl: "https://dashscope.aliyuncs.com/compatible-mode/v1" },
  { label: "Kimi (Moonshot)", baseUrl: "https://api.moonshot.cn/v1" },
  { label: "OpenAI", baseUrl: "https://api.openai.com/v1" },
  { label: "Ollama (本地)", baseUrl: "http://localhost:11434/v1" },
  { label: "LM Studio (本地)", baseUrl: "http://localhost:1234/v1" },
];

export function AssistantSettingsForm() {
  const { t } = useTranslation();
  const [baseUrl, setBaseUrl] = useState("");
  const [model, setModel] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [hasKey, setHasKey] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);

  // 载入已保存配置（key 只取 hasKey 布尔，不回显明文）
  // Load the saved config (the key only surfaces as a hasKey boolean, never as plaintext).
  useEffect(() => {
    assistantGetState()
      .then((info) => {
        setBaseUrl(info.baseUrl);
        setModel(info.model);
        setHasKey(info.hasKey);
      })
      .catch(() => {});
  }, []);

  const save = async () => {
    setSaving(true);
    try {
      // 空 key = 保留已存 key（后端 assistant_set_config 的语义）
      // Empty key = keep the stored key (the semantics of backend assistant_set_config).
      await assistantSetConfig(baseUrl.trim(), model.trim(), apiKey.trim() || undefined);
      setHasKey(hasKey || !!apiKey.trim());
      setApiKey("");
      message.success(t("assistant.settings.saved"));
    } catch (e) {
      message.error(String(e));
    } finally {
      setSaving(false);
    }
  };

  const test = async () => {
    setTesting(true);
    try {
      await save();
      const detail = await assistantTestConfig();
      message.success(`${t("assistant.settings.test_ok")} ${detail}`);
    } catch (e) {
      message.error(`${t("assistant.settings.test_fail")} ${String(e)}`);
    } finally {
      setTesting(false);
    }
  };

  return (
    <Form layout="vertical" size="small">
      <Form.Item label={t("assistant.settings.provider")}>
        <Select
          size="small"
          placeholder={t("assistant.settings.provider_placeholder")}
          allowClear
          onChange={(v) => {
            const preset = PROVIDER_PRESETS.find((p) => p.label === v);
            if (preset) setBaseUrl(preset.baseUrl);
          }}
          options={PROVIDER_PRESETS.map((p) => ({ label: p.label, value: p.label }))}
        />
      </Form.Item>
      <Form.Item label={t("assistant.settings.base_url")}>
        <Input
          size="small"
          value={baseUrl}
          onChange={(e) => setBaseUrl(e.target.value)}
          placeholder="https://api.deepseek.com"
        />
      </Form.Item>
      <Form.Item label={t("assistant.settings.model")}>
        <Input
          size="small"
          value={model}
          onChange={(e) => setModel(e.target.value)}
          placeholder="deepseek-chat"
        />
      </Form.Item>
      <Form.Item label={t("assistant.settings.api_key")}>
        <Input.Password
          size="small"
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
          placeholder={hasKey ? t("assistant.settings.key_kept") : "sk-…"}
          autoComplete="off"
        />
        <Text type="secondary" style={{ fontSize: 11 }}>
          {t("assistant.settings.key_hint")}
        </Text>
      </Form.Item>
      <div style={{ display: "flex", gap: 8 }}>
        <Button size="small" type="primary" loading={saving} onClick={save}>
          {t("assistant.settings.save")}
        </Button>
        <Button size="small" loading={testing} onClick={test}>
          {t("assistant.settings.test")}
        </Button>
      </div>
    </Form>
  );
}
