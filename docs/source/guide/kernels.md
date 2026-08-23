# SPICE 内核

星历动力学（轨道设计的星历修正、轨道保持等）需要 NASA SPICE 内核文件；
必需内核包括行星历（`.bsp`，如 `de440.bsp`）与闰秒（`.tls`，如
`naif0012.tls`）。

**轨道族生成与轨道库浏览不需要内核**：两者是纯 CR3BP 计算，安装后直接
使用，无任何内核准备步骤。轨道设计（星历修正）、轨道保持等星历类工具
运行时需要内核，按下文准备。

## 内核从哪里来

安装包已随带小内核（`.bpc` / `.tls` / `.tpc` / `.tf`，位于安装目录的
`resources/kernels/`）；体积大的星历 `.bsp` 不随包分发，需要时获取：

- **自动下载（推荐）**：`uv run python scripts/download_kernels.py`，幂等地
  拉取全部内核到 `kernels/`；
- **手动下载**：从 e2m2e 的
  [`kernels-v1` release](https://github.com/cislunarspace/e2m2e/releases)
  下载解压到 sidecar 工作目录下的 `kernels/`（开发期即仓库根 `kernels/`，
  安装版即安装目录）；
- **自备数据**：将 `$SPICE_KERNEL_DIR` 指向已有内核目录（优先级最高，sidecar
  进程继承该环境变量）。

官方来源：[NASA NAIF](https://naif.jpl.nasa.gov/naif/data.html)（备用）。

## 常见问题

- **报 "SPICE(NOLEAPSECONDS)"**：闰秒内核未加载。确保内核目录含
  `naif0012.tls`，或设置 `$SPICE_KERNEL_DIR` 后重启应用。
- **v3.2.3 及更早版本的 GUI 内核自动引导弹窗已随 PyQt UI 移除**；当前界面
  不再提供引导交互，需按上节手动准备内核。