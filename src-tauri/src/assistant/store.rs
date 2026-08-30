//! 助手配置、凭据与助手会话的落盘（本仓 ADR 0023 决策 6/7）。
//!
//! 目录约定与 Python 侧 `src/commons/paths.py` 的 user_config_dir() 一致：
//! Windows `%APPDATA%/transfer-orbit-design`，其他平台 XDG
//! `~/.config/transfer-orbit-design`。
//!
//! - 模型服务非密钥配置（base_url/model/全局默认思考等级）：`assistant.json`
//! - API key：OS keychain（keyring crate）；keychain 不可用时降级为
//!   `assistant.key` 明文文件（ADR 0023 决策 6 的降级路径）
//! - 助手会话（ADR 0025 决策 3）：`sessions/index.json` 存会话元数据，
//!   每会话一个 `<id>.jsonl`，一行一条记录——OpenAI 消息原样，思考行带
//!   `kind:"thinking"` 标记混入同一文件（构造 API 请求时过滤，ADR 0026 决策 5）
//!
//! 文件层核心函数一律以目录为参数（便于在临时目录单测）；模块级便捷封装
//! 固定用 [`config_dir`]。

use std::path::{Path, PathBuf};

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
    /// 全局默认思考等级（"off"/"standard"/"deep"；空 = 标准档，
    /// ADR 0026 决策 1：新会话继承此默认）。
    #[serde(default)]
    pub thinking_level: String,
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

// ---- 会话存储（ADR 0025 决策 3：index.json + 每会话 <id>.jsonl）----

/// 会话元数据（index.json 的数组元素；camelCase 即前端 SessionMeta 的传输形状）。
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SessionMeta {
    pub id: String,
    #[serde(default)]
    pub title: String,
    #[serde(default)]
    pub created_at: u64,
    #[serde(default)]
    pub updated_at: u64,
    #[serde(default)]
    pub message_count: u64,
    /// 本会话思考等级（"off"/"standard"/"deep"）；空 = 继承全局默认（ADR 0026 决策 1）。
    #[serde(default)]
    pub thinking_level: String,
}

pub fn unix_now() -> u64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0)
}

fn sort_latest_first(list: &mut [SessionMeta]) {
    list.sort_by_key(|m| std::cmp::Reverse(m.updated_at));
}

/// 读会话列表（按最近活动倒序）。无 index.json 时从目录里的 .jsonl 原地
/// 迁移生成（ADR 0025 决策 3：default.jsonl 原地变列表成员，不做数据转换）。
pub fn load_index(dir: &Path) -> Vec<SessionMeta> {
    if let Ok(s) = std::fs::read_to_string(dir.join("index.json")) {
        if let Ok(mut list) = serde_json::from_str::<Vec<SessionMeta>>(&s) {
            sort_latest_first(&mut list);
            return list;
        }
    }
    let list = migrate_index_from_files(dir);
    let _ = save_index(dir, &list);
    list
}

/// 写会话列表（保持最近活动倒序的不变量）。
pub fn save_index(dir: &Path, sessions: &[SessionMeta]) -> anyhow::Result<()> {
    std::fs::create_dir_all(dir)?;
    let mut list = sessions.to_vec();
    sort_latest_first(&mut list);
    std::fs::write(dir.join("index.json"), serde_json::to_string_pretty(&list)?)?;
    Ok(())
}

/// 迁移：扫描目录下全部 .jsonl，按文件内容与 mtime 重建元数据。
fn migrate_index_from_files(dir: &Path) -> Vec<SessionMeta> {
    let Ok(entries) = std::fs::read_dir(dir) else {
        return Vec::new();
    };
    let mut metas = Vec::new();
    for entry in entries.flatten() {
        let path = entry.path();
        if path.extension().and_then(|e| e.to_str()) != Some("jsonl") {
            continue;
        }
        let Some(id) = path.file_stem().and_then(|s| s.to_str()) else {
            continue;
        };
        let rows = load_rows(dir, id);
        let mtime = file_mtime_secs(&path);
        metas.push(SessionMeta {
            id: id.to_string(),
            title: auto_title(&rows),
            created_at: mtime,
            updated_at: mtime,
            message_count: rows.iter().filter(|r| r.get("role").is_some()).count() as u64,
            thinking_level: String::new(),
        });
    }
    metas
}

fn file_mtime_secs(path: &Path) -> u64 {
    std::fs::metadata(path)
        .and_then(|m| m.modified())
        .ok()
        .and_then(|t| t.duration_since(std::time::UNIX_EPOCH).ok())
        .map(|d| d.as_secs())
        .unwrap_or_else(unix_now)
}

/// 标题自动取首条用户消息前 20 字（ADR 0025 决策 4）。
fn auto_title(rows: &[Value]) -> String {
    rows.iter()
        .find(|r| r.get("role").and_then(Value::as_str) == Some("user"))
        .and_then(|r| r.get("content").and_then(Value::as_str))
        .map(|c| c.chars().take(20).collect())
        .unwrap_or_default()
}

/// 会话 id：毫秒时间戳（创建是用户动作，天然唯一且可读）。
pub fn new_session_id() -> String {
    let ms = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_millis())
        .unwrap_or(0);
    format!("s{ms}")
}

/// 新建会话：登记元数据（思考等级继承全局默认），返回其元数据。
pub fn create_session(dir: &Path, global_default_level: &str) -> anyhow::Result<SessionMeta> {
    let now = unix_now();
    let meta = SessionMeta {
        id: new_session_id(),
        title: String::new(),
        created_at: now,
        updated_at: now,
        message_count: 0,
        thinking_level: global_default_level.to_string(),
    };
    let mut sessions = load_index(dir);
    sessions.push(meta.clone());
    save_index(dir, &sessions)?;
    Ok(meta)
}

/// 追加一行（消息或思考行）到会话文件，并同步 index 元数据：最近活动、
/// 消息数（仅带 role 的行计数）、首条用户消息自动命名。持久化失败静默
/// ——不打断对话（与 ADR 0023 决策 7 的容错立场一致）。
pub fn append_row(dir: &Path, session_id: &str, row: &Value) {
    // 先读 index（无 index 时触发迁移——必须在写文件之前，否则迁移会把
    // 刚写入的行也计入，首条消息被计两次）
    let mut sessions = load_index(dir);
    let path = dir.join(format!("{session_id}.jsonl"));
    if let Some(parent) = path.parent() {
        let _ = std::fs::create_dir_all(parent);
    }
    let Ok(line) = serde_json::to_string(row) else {
        return;
    };
    use std::io::Write;
    if std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(&path)
        .and_then(|mut f| writeln!(f, "{line}"))
        .is_err()
    {
        return;
    }
    let now = unix_now();
    let meta = match sessions.iter_mut().find(|m| m.id == session_id) {
        Some(m) => m,
        None => {
            sessions.push(SessionMeta {
                id: session_id.to_string(),
                title: String::new(),
                created_at: now,
                updated_at: now,
                message_count: 0,
                thinking_level: String::new(),
            });
            sessions.last_mut().expect("刚 push")
        }
    };
    meta.updated_at = now;
    if row.get("role").is_some() {
        meta.message_count += 1;
    }
    if meta.title.is_empty() && row.get("role").and_then(Value::as_str) == Some("user") {
        if let Some(c) = row.get("content").and_then(Value::as_str) {
            meta.title = c.chars().take(20).collect();
        }
    }
    let _ = save_index(dir, &sessions);
}

/// 读回整段会话（消息行 + 思考行原样；坏行跳过：文件可能被外部截断/手写）。
pub fn load_rows(dir: &Path, session_id: &str) -> Vec<Value> {
    std::fs::read_to_string(dir.join(format!("{session_id}.jsonl")))
        .map(|s| {
            s.lines()
                .filter_map(|line| serde_json::from_str(line).ok())
                .collect()
        })
        .unwrap_or_default()
}

/// 清空会话内容（"清空重开"按钮）：删文件，保留会话元数据。
pub fn clear_rows(dir: &Path, session_id: &str) {
    let _ = std::fs::remove_file(dir.join(format!("{session_id}.jsonl")));
    let mut sessions = load_index(dir);
    if let Some(m) = sessions.iter_mut().find(|m| m.id == session_id) {
        m.message_count = 0;
        m.updated_at = unix_now();
    }
    let _ = save_index(dir, &sessions);
}

/// 删除会话：文件 + 元数据一起删。
pub fn delete_session(dir: &Path, session_id: &str) {
    let _ = std::fs::remove_file(dir.join(format!("{session_id}.jsonl")));
    let sessions: Vec<SessionMeta> = load_index(dir)
        .into_iter()
        .filter(|m| m.id != session_id)
        .collect();
    let _ = save_index(dir, &sessions);
}

/// 更新单个会话的元数据（重命名 / 设思考等级共用）。
fn update_meta(
    dir: &Path,
    session_id: &str,
    f: impl FnOnce(&mut SessionMeta),
) -> anyhow::Result<()> {
    let mut sessions = load_index(dir);
    let meta = sessions
        .iter_mut()
        .find(|m| m.id == session_id)
        .ok_or_else(|| anyhow::anyhow!("会话不存在：{session_id}"))?;
    f(meta);
    save_index(dir, &sessions)
}

pub fn rename_session(dir: &Path, session_id: &str, title: &str) -> anyhow::Result<()> {
    update_meta(dir, session_id, |m| m.title = title.trim().to_string())
}

pub fn set_thinking_level(dir: &Path, session_id: &str, level: &str) -> anyhow::Result<()> {
    update_meta(dir, session_id, |m| m.thinking_level = level.to_string())
}

// ---- 便捷封装：固定用用户配置目录 ----

fn sessions_dir() -> Option<PathBuf> {
    config_dir().map(|d| d.join("sessions"))
}

pub fn load_sessions() -> Vec<SessionMeta> {
    sessions_dir().map(|d| load_index(&d)).unwrap_or_default()
}

pub fn create_session_entry(global_default_level: &str) -> Option<SessionMeta> {
    let dir = sessions_dir()?;
    create_session(&dir, global_default_level).ok()
}

pub fn append_session_row(session_id: &str, row: &Value) {
    if let Some(dir) = sessions_dir() {
        append_row(&dir, session_id, row);
    }
}

pub fn load_session_rows(session_id: &str) -> Vec<Value> {
    sessions_dir()
        .map(|d| load_rows(&d, session_id))
        .unwrap_or_default()
}

pub fn clear_session_rows(session_id: &str) {
    if let Some(dir) = sessions_dir() {
        clear_rows(&dir, session_id);
    }
}

pub fn delete_session_entry(session_id: &str) {
    if let Some(dir) = sessions_dir() {
        delete_session(&dir, session_id);
    }
}

pub fn rename_session_entry(session_id: &str, title: &str) -> anyhow::Result<()> {
    sessions_dir()
        .ok_or_else(|| anyhow::anyhow!("无用户配置目录"))
        .and_then(|dir| rename_session(&dir, session_id, title))
}

pub fn set_session_thinking_level(session_id: &str, level: &str) -> anyhow::Result<()> {
    sessions_dir()
        .ok_or_else(|| anyhow::anyhow!("无用户配置目录"))
        .and_then(|dir| set_thinking_level(&dir, session_id, level))
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    struct TempDir(PathBuf);
    impl TempDir {
        fn new(tag: &str) -> Self {
            let dir = std::env::temp_dir().join(format!(
                "tod-assistant-store-test-{tag}-{}",
                std::process::id()
            ));
            let _ = std::fs::remove_dir_all(&dir);
            std::fs::create_dir_all(&dir).unwrap();
            Self(dir)
        }
    }
    impl Drop for TempDir {
        fn drop(&mut self) {
            let _ = std::fs::remove_dir_all(&self.0);
        }
    }

    use std::io::Write as _;

    fn write_lines(path: &Path, lines: &[String]) {
        let mut f = std::fs::File::create(path).unwrap();
        for l in lines {
            writeln!(f, "{l}").unwrap();
        }
    }

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
    fn rows_roundtrip_skips_bad_lines() {
        let dir = TempDir::new("roundtrip");
        let path = dir.0.join("default.jsonl");
        write_lines(
            &path,
            &[
                r#"{"role":"user","content":"你好"}"#.into(),
                "这不是 JSON 的坏行".into(),
                r#"{"kind":"thinking","content":"想一下"}"#.into(),
                r#"{"role":"assistant","content":"你好！"}"#.into(),
            ],
        );
        let rows = load_rows(&dir.0, "default");
        assert_eq!(rows.len(), 3, "坏行应被跳过");
        assert_eq!(rows[0]["role"], "user");
        assert_eq!(rows[1]["kind"], "thinking", "思考行原样读回");
    }

    #[test]
    fn append_updates_index_and_autotitles() {
        let dir = TempDir::new("append-index");
        append_row(
            &dir.0,
            "s1",
            &json!({"role": "user", "content": "帮我设计一条 DRO 轨道并给出参数"}),
        );
        append_row(
            &dir.0,
            "s1",
            &json!({"kind": "thinking", "content": "先查轨道库"}),
        );
        append_row(
            &dir.0,
            "s1",
            &json!({"role": "assistant", "content": "好的"}),
        );
        let list = load_index(&dir.0);
        assert_eq!(list.len(), 1, "append 应就地补建 meta");
        let m = &list[0];
        assert_eq!(m.id, "s1");
        assert_eq!(m.message_count, 2, "思考行不计入消息数");
        assert_eq!(
            m.title,
            "帮我设计一条 DRO 轨道并给出参数"
                .chars()
                .take(20)
                .collect::<String>()
        );
        // 追加一行消息验证 updated_at 走在 created_at 之后、消息数递增
        std::thread::sleep(std::time::Duration::from_millis(1100));
        append_row(&dir.0, "s1", &json!({"role": "user", "content": "第二条"}));
        let list = load_index(&dir.0);
        assert_eq!(list[0].message_count, 3);
        assert!(list[0].updated_at >= list[0].created_at);
    }

    #[test]
    fn migrates_default_jsonl_in_place() {
        let dir = TempDir::new("migrate");
        write_lines(
            &dir.0.join("default.jsonl"),
            &[
                r#"{"role":"user","content":"旧会话的第一条消息"}"#.into(),
                r#"{"role":"assistant","content":"回复"}"#.into(),
            ],
        );
        let list = load_index(&dir.0);
        assert_eq!(list.len(), 1);
        assert_eq!(list[0].id, "default");
        assert_eq!(list[0].title, "旧会话的第一条消息");
        assert_eq!(list[0].message_count, 2);
        // index.json 已落盘，二次读取一致（不再扫描）
        let again = load_index(&dir.0);
        assert_eq!(again.len(), 1);
        assert_eq!(again[0].id, "default");
        // 迁移不转换数据：原文件内容原样可读
        assert_eq!(load_rows(&dir.0, "default").len(), 2);
    }

    #[test]
    fn create_rename_delete_session_lifecycle() {
        let dir = TempDir::new("lifecycle");
        let meta = create_session(&dir.0, "deep").unwrap();
        assert_eq!(meta.thinking_level, "deep", "新会话继承全局默认档位");
        assert!(meta.title.is_empty());
        set_thinking_level(&dir.0, &meta.id, "off").unwrap();
        rename_session(&dir.0, &meta.id, "DRO 调参").unwrap();
        let list = load_index(&dir.0);
        assert_eq!(list[0].title, "DRO 调参");
        assert_eq!(list[0].thinking_level, "off");
        assert!(
            rename_session(&dir.0, "no-such", "x").is_err(),
            "改不存在的会话要报错"
        );
        delete_session(&dir.0, &meta.id);
        assert!(load_index(&dir.0).is_empty());
        assert!(load_rows(&dir.0, &meta.id).is_empty(), "会话文件应一并删除");
    }

    #[test]
    fn clear_rows_keeps_meta_but_empties_content() {
        let dir = TempDir::new("clear");
        append_row(&dir.0, "s1", &json!({"role": "user", "content": "hi"}));
        clear_rows(&dir.0, "s1");
        assert!(load_rows(&dir.0, "s1").is_empty());
        let list = load_index(&dir.0);
        assert_eq!(list.len(), 1, "清空保留会话本身");
        assert_eq!(list[0].message_count, 0);
    }

    #[test]
    fn index_sorted_latest_first() {
        let dir = TempDir::new("sort");
        let mut older = create_session(&dir.0, "").unwrap();
        older.updated_at = 100;
        let newer = create_session(&dir.0, "").unwrap();
        let newer_id = newer.id.clone();
        save_index(&dir.0, &[older, newer]).unwrap();
        let list = load_index(&dir.0);
        assert_eq!(list[0].id, newer_id, "最近活动的会话排最前");
    }
}
