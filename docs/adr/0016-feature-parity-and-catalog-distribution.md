# 0016. 功能补齐验收基准与 catalog 工具分布规范

- 日期: 2025-02-24
- 状态: 提议 (Accepted)

## 上下文

为解决迁移后功能丢失与界面简陋的问题，需要明确补齐的验收基准，以及 e2m2e 提供的 14 个已注册工具在 Tauri GUI 中的界面布局分布规范。

## 决策

1. **验收基准**：
   - 严格以 [docs-old-pyqt-gui-inventory.md](../../docs-old-pyqt-gui-inventory.md) 记录的 24 项迁移丢失功能清单为底账。
   - 每一项必须在 Tauri 架构中具备对等能力（交互形式可优化为现代 Web 范式，但能力不得缺失）。
   - 5 个 e2m2e 占位符工具（`transfer_search`, `low_thrust_design`, `manifold_analysis`, `low_energy_transfer`, `relative_motion`）在上游正式实现前明确排除，不阻塞本轮验收。

2. **工具界面分布规范**：
   - **中栏工具面板**：承载 8 个生成/计算工具——7 个核心动力学工具（`design_orbit`, `orbit_family_generation`, `control_orbit`, `orbit_propagation`, `transfer_design`, `orbit_stability`, `spacetime_transform`）+ `catalog_sweep`（参数扫描批量生成）。
   - **左栏过滤栏**：承载 `catalog_query` 过滤表单与 `catalog_export`（教学案例包导出）按钮。
   - **左栏项目树与右键菜单**：承载 `catalog_get`（查看/叠加渲染）、`catalog_delete`（右键物理删除含确认框）、`orbit_stability`（右键查看稳定性）。
   - **左栏记录详情面板**：承载 `catalog_tag`（编辑标签/笔记）、`catalog_promote`（族成员提升为独立记录）、谱系断链提示与独立轨道保持入口。
   - **右栏主画布**：恢复四投影（3D/XY/XZ/YZ/四视图）、坐标系（会合/惯性）、绘制中心（质心/月球/L1/L2）、时间轴拨动与参数化动画导出。

## 结果

- 建立了完全清晰、可逐项打勾的验收清单。
- 14 个 e2m2e 公开工具各司其职，完美融入三栏布局中，杜绝功能遗漏。
