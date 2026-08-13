# 快速上手

## 安装

项目要求 Python >= 3.13。用 [uv](https://docs.astral.sh/uv/) 安装：

```bash
uv sync
```

`uv sync` 一次完成解释器准备、虚拟环境创建与全部依赖安装（含核心算法库
`e2m2e>=5.6.8`）。

Windows 用户也可从
[GitHub Releases](https://github.com/cislunarspace/transfer-orbit-design/releases)
下载便携包 `TransferOrbitDesign-windows.zip`，解压即用，无需安装 Python。

## 启动

```bash
uv run transfer-orbit-design
```

首次启动时，程序会探测 SPICE 内核是否可用（见 {doc}`kernels`）。未找到可用
内核会自动弹窗引导，三种选择：

- **下载内核**：从 e2m2e 的 `kernels-v1` release 一键下载（带进度条），
  下载到用户数据目录，跨版本共享；
- **指定已有目录**：选择你已有的内核目录（含行星历 `.bsp` 与闰秒 `.tls`），
  选择后自动记忆，下次启动直接使用；
- **暂时跳过**：本次不准备，用到星历功能时再报错提示。

## 一次轨道设计操作

界面为三栏布局：左侧项目树、中间可视化画布与日志标签页、右侧工具选择器与
参数面板。

1. 右侧工具选择器选**轨道设计**，选轨道类型（DRO / Halo / NRHO / Lissajous /
   L4 / L5 / ELFO）并填参数。
2. 点击**运行**，计算在后台线程执行，日志面板逐条输出进度。
3. 完成后结果以 JSON + NPZ 双文件落盘 `output/`，轨道随即叠加显示在画布上。

## 从已有结果继续

启动时会自动扫描 `output/` 目录，把历史结果重建为**工件**（Artifact）显示在
左侧项目树中。右键选中工件即可发起后续操作：

- 对单条轨道：**轨道保持**（以选中轨道星历为输入做蒙特卡洛仿真）、
  **稳定性分析**（Floquet 乘子 / 稳定性指数）；
- Ctrl+点击多选轨道可叠加对比。

四个工具的完整参数说明见 {doc}`tools`。
