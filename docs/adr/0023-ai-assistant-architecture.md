# ADR 0023：AI 助手架构——Rust 宿主 agent loop 与标准 MCP 拓扑

**状态**：已接受
**日期**：2026-08-29
**关联**：ADR 0022（功能定位与模型服务策略）；ADR 0019（sidecar 子树生命周期，mcp-serve 进程沿用同一套管理）；e2m2e ADR 0014/0035（两条 stdio 链路的分工）

## 背景

ADR 0022 确定了 AI 助手的定位，实现层面需要回答：agent loop（LLM 对话循环与工具调用编排）写在哪一层、工具调用走哪条通道、凭据与会话存哪。事实前提：e2m2e 有两条独立 stdio 链路——现有 GUI 用的 `serve-stdio`（e2m2e 自有协议：JSON 行＋二进制帧＋进度事件，常驻**串行**单例）与标准 MCP 的 `mcp-serve`（纯文本通道，同步计算在线程池执行，可并发）；Rust 端当时无 HTTP client（tokio 未开 net）；`[mcp]` extra（`mcp>=2.0`）尚未进入本仓依赖与 PyInstaller 打包；配置目录先例为 `%APPDATA%/transfer-orbit-design`（Python 侧 `user_config_dir()`）。

## 决策

1. **agent loop 宿主**：Rust 后端。新增 HTTP client（reqwest）调 LLM（SSE 流式），流式增量经 Tauri event 推前端（`sidecar-progress` 同款模式）；API key 不进 webview JS 上下文。
2. **MCP 拓扑**：工具调用走标准 MCP——Rust 实现最小 MCP stdio client（initialize / tools/list / tools/call 三个方法的 JSON-RPC），连 `mcp-serve` 常驻进程；进程管理沿用 ADR 0019 的懒启动＋崩溃自愈＋Job Object 兜底。`[mcp]` extra 加入 `pyproject.toml` 与 PyInstaller spec（hiddenimports 收编 `e2m2e.api.mcp`）。
3. **并发语义**：AI 的只读查询（mcp-serve 线程池）与 GUI 正在跑的计算（serve-stdio 串行单例）互不阻塞；两条进程并存。
4. **验证链**：工具调用请求与结果经过一条可插拔检查链——Pydantic 参数校验（MCP 信封层已有）＋ ADR 0022 决策 4 的分级确认；物理可行性等专用验证器后补（模式三场景层）。
5. **摘要层与上下文契约**：工具结果进 LLM 上下文前必须过摘要/投影——MCP 是纯文本通道，轨迹数组等大体量数据不进上下文；轨迹入轨道库，上下文只带 `record_id`、状态与诊断摘要。注入 LLM 的轨道库清单用摘要形式（族、平动点、Jacobi、谱系），轨道状态序列化带量纲、历元（UTC）与来源记录 id。助手可见上下文＝工具清单与参数 schema＋轨道库摘要＋**当前选择 Artifact**（不含画布实时状态）。
6. **凭据存储**：API key 存 OS keychain（`keyring` crate，三平台有后端）；keychain 不可用时降级为 `%APPDATA%/transfer-orbit-design` 下的配置文件。
7. **会话持久化**：`%APPDATA%/transfer-orbit-design/sessions/<id>.jsonl`（遵循 `user_config_dir()` 先例）；v1 为单条持久会话（固定 id，可清空重开），存储格式预留多会话扩展。
8. **前端形态**：主布局新增右侧可折叠 **助手边栏**（宽度可拖，折叠状态 localStorage 持久化）；未配置模型服务时边栏空态显示配置引导（指向设置面板 AI 助手分区）；工具调用以 **工具卡片** 呈现在对话流中（工具名、参数摘要、运行状态、结果与"已入轨道库/已上画布"跳转），详细日志仍进现有日志视图；新增 markdown 渲染依赖。

## 考虑过的选项

- **复用 serve-stdio 通道跑 agent loop**（否决）：串行单例意味着 AI 的只读查询要排在用户长计算后面；且非标准 MCP，无运行时工具发现，不符合"LLM+MCP"的目标与上游 ADR 0014 愿景。
- **Python sidecar 宿主 agent loop**（否决）：官方 mcp/openai SDK 现成，但要把 AI 功能塞进 e2m2e 的 PyInstaller 运行时（加依赖与 hiddenimports），关注点错位、打包更重、key 管理更弱。
- **前端 TS 直连 LLM**（否决）：key 暴露在 webview JS 上下文、需放宽 CSP；stdio 不可达，进程管理仍要 Rust 中转。

## 后果

- 新增一个常驻 Python 进程（mcp-serve）的内存开销，与 serve-stdio 并存。
- **已知限制**：`mcp-serve` 目前不转发进度事件（同步计算在线程池跑完才返回），AI 触发的长计算 v1 在工具卡片上只显示不定态运行指示与耗时；`mcp-serve` 同样未实现 MCP 取消通知，已确认开始的 AI 工具运行 v1 不可中断。二者均属 e2m2e 上游后续工作。
- 打包：Rust 端新增 reqwest/keyring；sidecar spec 新增 `[mcp]` extra 与 hiddenimports；前端新增 markdown 渲染库。release workflow 结构不变。
- 前端状态管理仍为 App.tsx 集中的 hooks；边栏状态沿此模式，不引入状态库。
