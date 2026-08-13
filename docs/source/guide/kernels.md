# SPICE 内核

星历动力学（轨道设计的星历修正、轨道保持）需要 NASA SPICE 内核文件。
e2m2e 的 SPICE 内核不随 pip 包分发——大文件托管在 e2m2e 仓库的
[`kernels-v1` release](https://github.com/cislunarspace/e2m2e/releases) 中，
需要宿主自行准备。必需内核包括行星历（`.bsp`，如 `de440.bsp`）与闰秒
（`.tls`，如 `naif0012.tls`）。

## GUI 自动引导

**GUI 启动时探测不到可用内核会自动弹窗引导**，三种选择：

| 选项 | 行为 |
|------|------|
| 下载内核 | 后台线程从 e2m2e `kernels-v1` release 下载到用户数据目录（Linux/macOS `~/.local/share/transfer-orbit-design/kernels`，Windows `%LOCALAPPDATA%`），模态进度条逐文件显示进度，可取消（已下载文件保留，重试幂等续传）；下载目录跨版本共享 |
| 指定已有目录 | 文件选择对话框选目录，校验含行星历 `.bsp` 与闰秒 `.tls` 后写入配置文件（`~/.config/transfer-orbit-design/kernels_dir.txt`），下次启动自动探测 |
| 暂时跳过 | 本次不准备，用到星历功能时再报错提示 |

内核探测顺序：`$SPICE_KERNEL_DIR` 环境变量 → 配置文件记录 → 仓库 `kernels/`
目录 → 用户数据目录 → 同级 e2m2e 源码仓库的 `kernels/`。目录存在但缺必需
内核文件同样视为不可用。

## 命令行 / 脚本方式

脚本化场景可用以下方式之一：

- **自动下载（推荐）**：`python scripts/download_kernels.py`，幂等地拉取
  全部内核到 `kernels/`；
- **手动下载**：从上述 release 下载解压到 `kernels/` 目录；
- **自备数据**：使用自己的内核文件，或将 `$SPICE_KERNEL_DIR` 指向其所在路径。

官方来源：[NASA NAIF](https://naif.jpl.nasa.gov/naif/data.html)（备用）。

## 常见问题

- **轨道设计报 "SPICE(NOLEAPSECONDS)"**：闰秒内核未加载。确保内核目录含
  `naif0012.tls`，或在启动前设置 `$SPICE_KERNEL_DIR`（必须在 import e2m2e
  之前生效，GUI 已自动处理）。
- **纯 CR3BP 功能不需要内核**：轨道族生成、稳定性分析是纯 CR3BP 计算，
  内核缺失不影响。
