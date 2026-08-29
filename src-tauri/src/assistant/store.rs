//! 助手配置、凭据与助手会话的落盘（本仓 ADR 0023 决策 6/7）。
//!
//! 目录约定与 Python 侧 `src/commons/paths.py` 的 user_config_dir() 一致：
//! Windows `%APPDATA%/transfer-orbit-design`，其他平台 XDG
//! `~/.config/transfer-orbit-design`。
//!
//! - 模型服务非密钥配置（base_url/model）：`assistant.json`
//! - API key：OS keychain（keyring crate）；keychain 不可用时降级为
//!   `assistant.key` 明文文件（ADR 0023 决策 6 的降级路径）
//! - 助手会话：`sessions/default.jsonl`，一行一条 OpenAI 消息（v1 单会话
//!   固定 id=default；文件名即会话 id，多会话扩展只换文件名）

use std::path::PathBuf;

use serde_json::Value;

/// 用户配置目录（与 Python 侧 user_config_dir() 同路径）。取不到 HOME/
/// APPDATA 时返回 None——调用方按"无持久化"降级（功能可用，重启丢）。
pub fn config_dir() -> Option<PathBuf> {
    #[cfg(windows)]
    let base = std::env::var_os("APPDATA").map(PathBuf::from);
    #[cfg(not(windows))]
    let base = std::env::var_os("XDG_CONFIG_HOME")
        .map(PathBuf::from)
        .or_else(|| std::env::var_os("HOME").map(|h| PathBuf::from(h).join(".config")));
    base.map(|b| b.join("transfer-orbit-design"))
}

/// 模型服务配置（非密钥部分）。key 永不进此结构、不落此文件。
#[derive(Debug, Clone, Default, serde::Serialize, serde::Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ModelConfig {
    #[serde(default)]
    pub base_url: String,
    #[serde(default)]
    pub model: String,
}

impl ModelConfig {
    /// 可用判定：base_url 与 model 均非空（key 单独检查）。
    pub fn is_complete(&self) -> bool {
        !self.base_url.trim().is_empty() && !self.model.trim().is_empty()
    }
}

fn config_path() -> Option<PathBuf> {
    config_dir().map(|d| d.join("assistant.json"))
}

pub fn load_model_config() -> ModelConfig {
    config_path()
        .and_then(|p| std::fs::read_to_string(p).ok())
        .and_then(|s| serde_json::from_str(&s).ok())
        .unwrap_or_default()
}

pub fn save_model_config(cfg: &ModelConfig) -> anyhow::Result<()> {
    let path = config_path().ok_or_else(|| anyhow::anyhow!("无用户配置目录"))?;
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)?;
    }
    std::fs::write(path, serde_json::to_string_pretty(cfg)?)?;
    Ok(())
}

const KEYRING_SERVICE: &str = "transfer-orbit-design";
const KEYRING_ACCOUNT: &str = "assistant-api-key";

/// 存 API key：keychain 优先，失败降级明文文件（ADR 0023 决策 6）。
pub fn save_api_key(key: &str) -> anyhow::Result<()> {
    match keyring::Entry::new(KEYRING_SERVICE, KEYRING_ACCOUNT) {
        Ok(entry) if entry.set_password(key).is_ok() => {
            // keychain 成功后清掉可能存在的降级文件，避免两份漂移
            if let Some(p) = config_dir().map(|d| d.join("assistant.key")) {
                let _ = std::fs::remove_file(p);
            }
            Ok(())
        }
        _ => {
            let dir = config_dir().ok_or_else(|| anyhow::anyhow!("无用户配置目录"))?;
            std::fs::create_dir_all(&dir)?;
            std::fs::write(dir.join("assistant.key"), key)?;
            Ok(())
        }
    }
}

/// 取 API key：keychain 优先，回落降级文件；都没有返回 None。
pub fn load_api_key() -> Option<String> {
    if let Ok(entry) = keyring::Entry::new(KEYRING_SERVICE, KEYRING_ACCOUNT) {
        if let Ok(key) = entry.get_password() {
            if !key.is_empty() {
                return Some(key);
            }
        }
    }
    config_dir()
        .map(|d| d.join("assistant.key"))
        .and_then(|p| std::fs::read_to_string(p).ok())
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
}

fn session_path() -> Option<PathBuf> {
    config_dir().map(|d| d.join("sessions").join("default.jsonl"))
}

/// 追加一条会话记录（OpenAI 消息原样一行）。持久化失败不打断对话。
pub fn append_session(message: &Value) {
    let Some(path) = session_path() else { return };
    if let Some(parent) = path.parent() {
        let _ = std::fs::create_dir_all(parent);
    }
    if let Ok(line) = serde_json::to_string(message) {
        use std::io::Write;
        if let Ok(mut f) = std::fs::OpenOptions::new().create(true).append(true).open(path) {
            let _ = writeln!(f, "{line}");
        }
    }
}

/// 读回整段会话（坏行跳过：文件可能被外部截断/手写）。
pub fn load_session() -> Vec<Value> {
    session_path()
        .and_then(|p| std::fs::read_to_string(p).ok())
        .map(|s| {
            s.lines()
                .filter_map(|line| serde_json::from_str(line).ok())
                .collect()
        })
        .unwrap_or_default()
}

/// 清空会话（"清空重开"按钮）。
pub fn clear_session() {
    if let Some(path) = session_path() {
        let _ = std::fs::remove_file(path);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn model_config_completeness() {
        let mut cfg = ModelConfig::default();
        assert!(!cfg.is_complete());
        cfg.base_url = "https://api.deepseek.com/v1".into();
        assert!(!cfg.is_complete());
        cfg.model = "deepseek-chat".into();
        assert!(cfg.is_complete());
    }

    #[test]
    fn session_roundtrip_in_temp_dir() {
        // 直接测文件层语义：写两行、读回、清空
        let dir = std::env::temp_dir().join("tod-assistant-store-test");
        let path = dir.join("sessions").join("default.jsonl");
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(path.parent().unwrap()).unwrap();
        use std::io::Write;
        let mut f = std::fs::File::create(&path).unwrap();
        writeln!(f, r#"{{"role":"user","content":"你好"}}"#).unwrap();
        writeln!(f, "这不是 JSON 的坏行").unwrap();
        writeln!(f, r#"{{"role":"assistant","content":"你好！"}}"#).unwrap();
        drop(f);
        let lines: Vec<Value> = std::fs::read_to_string(&path)
            .unwrap()
            .lines()
            .filter_map(|l| serde_json::from_str(l).ok())
            .collect();
        assert_eq!(lines.len(), 2, "坏行应被跳过");
        assert_eq!(lines[0]["role"], "user");
        let _ = std::fs::remove_dir_all(&dir);
    }
}
