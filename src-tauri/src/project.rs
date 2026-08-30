//! 项目状态：会话内 Artifact 容器。
//!
//! Artifact 摘要进内存（轻量）；大数组（帧）不入容器，由画布按需
//! 取用，族生成结果缓存在 command 返回前直接交付前端。

use std::sync::atomic::{AtomicU64, Ordering};

use serde::{Deserialize, Serialize};
use tokio::sync::Mutex;

/// Artifact 摘要（轻量形态，不含数组字段）。
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ArtifactSummary {
    pub artifact_id: String,
    /// "orbit" | "family" | "transfer" | "ephemeris"
    pub artifact_type: String,
    pub label: String,
    pub orbit_type: String,
    pub source_tool: String,
    pub record_id: Option<String>,
    pub created_at: String,
}

#[derive(Default)]
pub struct ProjectState {
    artifacts: Mutex<Vec<ArtifactSummary>>,
    counter: AtomicU64,
}

impl ProjectState {
    pub fn new() -> Self {
        Self::default()
    }

    pub async fn add(&self, mut a: ArtifactSummary) -> ArtifactSummary {
        let id = self.counter.fetch_add(1, Ordering::Relaxed);
        a.artifact_id = format!("a{id:03}");
        self.artifacts.lock().await.push(a.clone());
        a
    }

    pub async fn list(&self) -> Vec<ArtifactSummary> {
        self.artifacts.lock().await.clone()
    }

    pub async fn remove(&self, artifact_id: &str) -> bool {
        let mut guard = self.artifacts.lock().await;
        let len_before = guard.len();
        guard.retain(|a| a.artifact_id != artifact_id);
        len_before != guard.len()
    }
}