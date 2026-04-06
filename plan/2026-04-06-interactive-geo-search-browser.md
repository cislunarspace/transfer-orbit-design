# 为 plot_search_results_geo.py 添加交互式轨道遍历模式

## 目标
添加 `--interactive` 参数，按转移时间排序可行解，交互式逐条浏览转移轨道（参考 `plot_interactive_orbit_inspector.py` 的交互模式）。

## 任务列表

- [x] 1. **添加 `--interactive` CLI 参数和交互循环入口** `scripts/transfer/plot_search_results_geo.py`
  - 新增 `--interactive` flag
  - 在 main() 中添加 interactive 分支：加载 DRO → 构建 TransferSearch → 调用 `interactive_browse_by_time`

- [x] 2. **实现交互式遍历函数 `interactive_browse_by_time`** `scripts/transfer/plot_search_results_geo.py`
  - 按 `plt.ion()` + 键盘命令模式（Enter/q/s N/j N/r）
  - 每步：打印轨道信息 → 重新积分 → 3D 绘图（复用 `_plot_single_transfer_orbit` 等）
  - 按 transfer_time 排序可行解
