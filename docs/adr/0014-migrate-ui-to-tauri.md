# ADR-0014：UI 迁移到 Tauri 架构

## 日期

2026-08-05

## 状态

已接受

## 背景

tod 当前的 GUI 是 PyQt6 + matplotlib（约 1.2 万行 Python，四层架构见 `docs/architecture/architecture.md`）。维护痛点集中在：

- 控件状态管理分散在 Qt 信号/槽里，跨面板联动容易踩坑；
- QThread 工作线程与 GUI 线程边界需要手工维护；
- 样式与国际化缺少现成生态，大量手搓。

用户决定迁移到 Tauri 2 架构（参照 ~/codes/altgo）：Rust 后端 + React/TS 前端 + IPC。

## 决策

1. **架构选型**：Tauri 2（Rust 壳 + React/Vite 前端）。UI 本身不是 Rust 写的；Rust 承担进程编排、落盘、catalog 逻辑，前端承担全部控件。
2. **e2m2e 保持在 Python**：它依赖 calcephpy/SPICE，Rust 无法直接调用。将其作为 sidecar 子进程，提供薄 RPC 入口（stdin/stdout JSON 行协议），Rust 侧拉起、派发任务、转发进度事件。
3. **画布用 Three.js**：matplotlib 3D 无现成等价物，视图适配、视图保持、地月标注、GIF 导出需从头实现。此块是最大风险，先行原型验证。
4. **分阶段迁移**，旧 PyQt UI 保留至核心功能（项目树、参数面板、执行状态、画布）对齐：
   - 阶段 1：Tauri 脚手架 + Three.js 画布原型（星历轨迹 + 地月标注 + 交互），验证可行性；
   - 阶段 2：sidecar RPC 协议，跑通一个轨道族生成任务；
   - 阶段 3：核心 UI（项目树、参数面板、执行状态），参数面板由 Pydantic 模型转 JSON Schema 自动生成表单；
   - 阶段 4：长尾（catalog 过滤、GIF 导出、i18n、设置持久化），完成后移除 PyQt UI。
5. **术语表（CONTEXT.md）继续适用**：视图适配、视图保持、轨道族等领域语义在新 UI 中原样保留，不因换框架改名。

## 后果

- 状态管理收敛到前端 store，线程边界交给 tokio + Tauri 事件，预期显著降低维护成本；
- 画布是最大工作量单块（估计占四成以上），阶段 1 不通过则重新评估方案；
- 双 UI 并存期间有重复维护成本，阶段 4 完成前不移除旧 UI；
- 新增 Rust / TypeScript 技术栈，构建链变长（cargo + vite）。
