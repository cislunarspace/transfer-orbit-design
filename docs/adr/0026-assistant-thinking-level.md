# ADR 0026：AI 助手思考等级与过程展示

**状态**：已接受
**日期**：2026-08-30
**关联**：ADR 0022（决策 5 模型服务策略：首期 OpenAI 兼容协议）；ADR 0023（agent loop 与事件协议宿主）；ADR 0025（思考块持久化依赖其会话存储演进）

## 背景

两个需求：一是**思考等级调整**——BYOK 下各家 OpenAI 兼容服务的思考参数并不统一（DeepSeek 用 `thinking:{type}`，通义/百炼用 `enable_thinking`+`thinking_budget`，Kimi 只有 `thinking` 开关，OpenAI 系用 `reasoning_effort`）；二是**过程展示**——思考过程与工具调用要在消息流中可见（演示场景的核心卖点，呼应模式三"语言规划器"叙事）。

现状是纯绿地：LLM 请求体仅 `model/messages/stream/tools` 四个字段，SSE 解析只取 `delta.content` 与 `tool_calls`；事件协议 7 种 kind 无思考增量；前端无思考渲染分支；i18n 无相关键。抽象方法借鉴 cc-switch 的成熟实践：**统一档位枚举 × 按平台（base_url）判定的方言映射 × 收敛钳制**，纪律为"平台优先于模型、无证据的参数宁可不填"。

## 决策

1. **三档抽象**：关 / 标准 / 深度。控件粒度为每会话——输入区旁小三档单选，切会话记住各自档位；设置面板 AI 助手分区存全局默认，新会话继承。
2. **provider 映射表**（按 base_url 判定平台，判定不到走兜底）：

   | Provider（base_url） | 关 | 标准 | 深度 |
   |---|---|---|---|
   | DeepSeek（`api.deepseek.com`） | `thinking:{type:"disabled"}` | `thinking:{type:"enabled"}` | 标准 + `reasoning_effort:"high"` |
   | 通义/百炼（`dashscope.aliyuncs.com`） | `enable_thinking:false` | `enable_thinking:true` | 标准 + `thinking_budget:16384` |
   | Kimi（`api.moonshot.cn`） | `thinking:{type:"disabled"}` | `thinking:{type:"enabled"}` | 同标准（无强度旋钮，两档合并） |
   | Ollama / LM Studio / 未识别 | `reasoning_effort:"none"` | `reasoning_effort:"low"` | `reasoning_effort:"high"`（容忍被服务端忽略） |

   纪律：**标准档不发强度参数**（只开思考，用服务端默认强度），深度档才显式给强度；识别不了的 provider 只发 OpenAI 风格 `reasoning_effort`，不造假参数；只有开关的 provider（Kimi）标准与深度如实合并。
3. **思考流式增量按方言解析**：DeepSeek/通义回 `delta.reasoning_content`，MiniMax 回 `reasoning_details`；SSE 解析层新增对应分支，事件协议新增思考增量 kind（与 `delta` 并列）。
4. **展示架构**：思考块与工具卡片按发生顺序交织进消息流时间线，不分设侧面板——过程与结果同一条时间线，才对照得上"哪次调用产出了哪段正文"。思考块默认折叠（标题显示"已思考"），点击展开全文；完成的工具卡片折叠为单行摘要（工具名 + 状态 + record_id），点击展开参数与结果摘要。
5. **思考持久化分层**：展示层存全量（思考块随 ADR 0025 的会话文件落盘供回看），构造 API 请求回放时剥除——多数 provider 协议明确要求思考块不回放，这是硬约束不是偏好。
6. **映射参数被服务端拒绝**（如通义不认 `thinking_budget`）时不做自动降级重试，报错如实进消息流——错误自纠是 agent 职责（prompt 任务层已有"错误自纠≤3"），静默降级违背 ADR 0020 系列"不隐式降级"的一贯立场。

## 考虑过的选项

- **原生参数透传**（设置面板让用户自己填参数串，否决）：每次切 provider 都要用户去查对方文档，违背 BYOK"一套协议覆盖"的初衷（ADR 0022 决策 5）。
- **过程分离侧面板**（否决）：思考/工具与正文拆开，用户对照不上过程与结果的因果。
- **思考过程不持久化**（否决）：演示中"展示 AI 的推理过程"本身是卖点；回放剥离已解决协议约束，丢展示层没有收益。
- **每条消息一个档位**（否决）：粒度没有真实用户，每会话已覆盖演示现场调档位的需求。

## 后果

- `llm.rs` 的请求体构造与 SSE 解析都长出方言层，新增按 base_url 的 provider 判定表；Anthropic 原生协议的 `thinking:{budget_tokens}` 属 ADR 0022 决策 5 的后续协议扩展，不在本 ADR 范围。
- 一整条竖井的改动面：Rust（参数映射、SSE 新分支、新事件 kind）→ `chatModel`（思考块入消息模型）→ `ChatView`/`ToolCardView`（折叠渲染）→ i18n（中英键同步）。
- 已知限制新增一条：未识别 provider 的思考等级是"尽力而为"——`reasoning_effort` 可能被静默忽略，界面不保证思考块一定出现。
