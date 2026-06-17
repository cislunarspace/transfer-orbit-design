# Triage 标签

五个标签驱动 triage 状态机。它们必须存在于 GitHub 仓库中；若缺失，用 `gh label create` 创建。

| 标签 | 角色 | 含义 |
|-------|------|---------|
| `needs-triage` | 入口 | 维护者需要评估此 issue |
| `needs-info` | 阻塞 | 等待提交者补充信息 |
| `ready-for-agent` | 就绪（agent） | 已充分定义；AFK agent 无需额外人工上下文即可接手 |
| `ready-for-human` | 就绪（人工） | 需要人工实现 |
| `wontfix` | 关闭 | 不会处理 |

## 状态机

```
[新 issue] → needs-triage
needs-triage → needs-info        （提交者需要澄清）
needs-triage → ready-for-agent   （已充分定义，可交给 AFK agent）
needs-triage → ready-for-human   （需要人工动手）
needs-triage → wontfix           （超出范围 / 拒绝）
needs-info → needs-triage        （提交者已回复，重新评估）
needs-info → wontfix             （合理时间后无响应）
ready-for-agent → （issue 关闭） （agent 完成工作）
ready-for-human → （issue 关闭） （人工完成工作）
```

## 标签颜色（建议）

| 标签 | 颜色 |
|-------|--------|
| `needs-triage` | `#fbca04`（黄） |
| `needs-info` | `#006b75`（青） |
| `ready-for-agent` | `#0e8a16`（绿） |
| `ready-for-human` | `#1d76db`（蓝） |
| `wontfix` | `#b60205`（红） |
