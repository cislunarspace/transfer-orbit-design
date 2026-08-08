# ADR 0012：GUI 卡顿与接口边界依赖 e2m2e 上游修复，本地不上子进程

**状态**：已接受（上游 #312/#313 均已关闭，结果见「后续更新」）
**日期**：2026-08-06
**关联**：ADR 0011（算法层直调）、e2m2e #312、e2m2e #313

## 后续更新（2026-08-08）

决策得到验证：上游两个 issue 均已关闭，冻窗已在本地根治。

- **卡顿（#313，已于 2026-08-07 关闭）**：e2m2e 分两步修复并已由本仓消费——5.6.0（`dee042d`）把 CR3BP 族延拓切到 Rust `propagate_cr3bp_stm_py`，scipy 那段 ~70s 塌到 ~1.5s（第一层）；5.6.1 给长期预报 `propagate_compiled` 补 `allow_threads`（第二层）。本仓 `pyproject.toml` 升至 `e2m2e>=5.6.0`、`uv.lock` 钉 5.6.1（issue #354，2026-08-08）。默认 DRO + 1 月 duration 复测：总耗时 23.4s、>2s 空档 0 次、最大空档 0.40s——冻窗消除。下文「负面」中的"短期仍卡 66s+"已不复存在。
- **更正背景一处误判**：背景称"星历段 `propagate_compiled`（释放 GIL）不阻塞"——这是当时的误判。`propagate_compiled` 同样死持 GIL（主循环未包 `py.allow_threads`），duration 拉长时它才是冻窗大头；即第二层。故实际修了两层，而非原以为的一层。
- **接口边界（#312，已于 2026-08-07 关闭）**：e2m2e Facade Response 已补齐 `mu/states/times/ephemeris` 几何字段，按原计划可退回 Facade、移除 algorithm 层直调（ADR 0011 缓解措施 3）。截至本次更新，`facade_bridge.py` 仍直调 algorithm 层，切换尚未完成——这是一次性清理，不阻塞功能。
- **QMovie 转圈缓解措施作废**：冻窗已根治，原「短期感知」缓解不再需要。

## 背景

2026-08-06 诊断出两个问题，根因都在 e2m2e 上游：

**一、GUI 生成轨道时卡顿（窗口无响应）。** `e2m2e` 的 `design_dro`（及共用 `_propagate_with_stm` 的 `design_lissajous / design_halo` 等）用 `scipy.solve_ivp` 跑带 STM 的积分，全程持有 GIL 约 66 秒（DRO duration=0.3 实测；cProfile `design_dro` cumtime 69.7s、`equations_with_stm` 调用 423 万次）。worker 线程持 GIL 期间，主线程 Qt 事件循环冻结，窗口拖不动、点击无反应，用户误判为崩溃、手动退出。星历段用 Rust `propagate_compiled`（释放 GIL）不阻塞——唯独 CR3BP 修正段没切 Rust。**而 e2m2e 已导出 Rust STM 积分器（`propagate_compiled_stm_py` / `propagate_with_stm_py`），未启用。**

**二、接口边界穿透（ADR 0011 的遗留）。** ADR 0011 决定 GUI 直调 algorithm 层，因为 Facade Response 剥离了几何数据；其缓解措施 3 写明"Facade 未来补全返回完整数据，可切换回 Facade"。此缺口现已具体化：`DesignOrbitResponse` 缺 `mu / states / times / ephemeris`，`ControlOrbitResponse` 缺 `controlled_states / controlled_times / mu`——下游画图、落盘、design→control 链式所需。

本地可选根治方案：`OrbitDesignWorker` 从 `QThread` 改 `QProcess` 子进程隔离，绕过 GIL（架构改动，中等规模，且需适配 PyInstaller 冻结 exe 下 `python -m` 不可行的问题）。

## 决策

**本地暂不上子进程隔离，两个问题都推 e2m2e 上游修复：**

- **卡顿（GIL）→ e2m2e #313**：把 `design_dro` 等的 STM 积分切到 Rust `propagate_compiled_stm_py`，释放 GIL。
- **接口边界 → e2m2e #312**：补齐 Facade Response 的几何字段。发版后本项目按 ADR 0011 缓解措施 3 退回 Facade，移除 algorithm 层直调。

## 理由

1. **不与上游重复**：GIL 的钥匙（Rust STM 积分器）e2m2e 已有，只是没接；本地子进程是绕路，上游切 Rust 才是正源。Facade Response 缺口同理——补字段是上游 Facade 的本职。
2. **子进程方案有固有代价**：QProcess + IPC（pack/unpack DTO）+ PyInstaller 打包适配（`--worker` 子命令），改动面不小；上游修好后这些全成废码。
3. **上游修好后更干净**：退回 Facade（接口整洁）+ Rust 积分（不卡），比"本地子进程 + 仍穿透 algorithm"两头凑更优。

## 后果

### 正面

- 本地零架构改动（与卡顿相关的代码不动）
- 上游修好后一次性解决卡顿 + 接口边界
- 不引入子进程 IPC 复杂度与打包适配

### 负面

- **短期 GUI 生成时仍卡 66s+**（等 #313 发版）
- **仍穿透 algorithm 层**（等 #312 发版）
- 依赖上游排期，不可自控

### 缓解措施

- **短期感知**：可给运行按钮加 C++ 转圈动画（`QMovie`），GIL 阻塞时动画照转，让"在计算"可见（独立小改动，不与上游冲突、不与子进程绑定）
- **兜底**：若 #313 长期阻塞或技术上不可行（如 Rust STM 不支持 events / 穿越点检测），回头评估本地子进程隔离
- **跟踪**：#312 / #313 进展决定何时退回 Facade；届时修订本 ADR 或新增 ADR 记录切换
