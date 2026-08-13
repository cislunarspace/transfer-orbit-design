# transfer-orbit-design - 地月空间轨道设计 GUI

[![Release](https://img.shields.io/github/v/release/cislunarspace/transfer-orbit-design?label=release)](https://github.com/cislunarspace/transfer-orbit-design/releases)
[![CI](https://img.shields.io/github/actions/workflow/status/cislunarspace/transfer-orbit-design/ci.yml?branch=master&label=CI)](https://github.com/cislunarspace/transfer-orbit-design/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.13%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)

中文 | [English](README.en.md)

transfer-orbit-design 是 [e2m2e](https://github.com/cislunarspace/e2m2e) 的 GUI 前端。e2m2e 提供地月空间轨道设计所需的动力学模型、修正器、延拓器与转移算法，本仓库把它们封装成可视化桌面应用。它不实现算法，只做三件事：调用（经 Facade API 发起计算）、管理（以 Project/Artifact 组织全部计算产物）、呈现（内嵌画布可视化结果）。用户通过"选工件 -> 选操作 -> 看结果"的三步交互完成轨道设计、轨道保持与结果检查。

## 安装

项目要求 Python >= 3.13。用 [uv](https://docs.astral.sh/uv/) 安装：

```bash
uv sync
```

`uv sync` 一次完成解释器准备、虚拟环境创建与全部依赖安装（含核心算法库 `e2m2e>=5.6.7`）。

Windows 用户也可从 [GitHub Releases](https://github.com/cislunarspace/transfer-orbit-design/releases) 下载便携包 `TransferOrbitDesign-windows.zip`，解压即用；另从 [`spice-data-v1`](https://github.com/cislunarspace/transfer-orbit-design/releases/tag/spice-data-v1) 下载 `spice-kernels.zip`，解压到 `TransferOrbitDesign.exe` 所在目录（得到 `kernels/` 子目录），启动时自动探测。

## SPICE 内核

星历动力学需要 NASA SPICE 内核文件。全部必需内核打包在 [e2m2e 的 `kernels-v1` release](https://github.com/cislunarspace/e2m2e/releases) 中。三种配置方式：

- **自动下载（推荐）**：`python scripts/download_kernels.py`，幂等地拉取全部内核到 `kernels/`。
- **手动下载**：从上述 release 下载解压到 `kernels/` 目录。
- **自备数据**：使用自己的内核文件，或将 `$SPICE_KERNEL_DIR` 指向其所在路径。

官方来源：[NASA NAIF](https://naif.jpl.nasa.gov/naif/data.html)（备用）。

## 快速开始

```bash
uv run transfer-orbit-design
```

界面为三栏布局：左侧项目树、中间可视化画布与日志标签页、右侧工具选择器、参数面板与运行按钮。

一次轨道设计操作流：

1. 右侧工具选择器选轨道设计，选轨道类型（DRO / Halo / NRHO 等）并填参数。
2. 点击运行，计算在后台线程执行，日志面板逐条输出进度。
3. 完成后结果以 JSON + NPZ 双文件落盘 `output/`，轨道随即叠加显示在画布上。

画布工具栏可切换 3D / XY / XZ / YZ 投影，开关地月天体与 L1-L5 平动点标注；Ctrl+点击项目树可多选轨道叠加对比。在项目树右键轨道可发起轨道保持与稳定性分析。

## 能力

**轨道设计**

- 周期轨道生成：DRO、NRHO、Halo、Lissajous、L4/L5，参数面板由 Pydantic 模型自动生成，结果 JSON + NPZ 双文件落盘。

**轨道维护与分析**

- 轨道保持：以选中轨道星历为输入做蒙特卡洛仿真，输出受控星历与速度增量统计。
- 轨道族生成：小振幅 Halo 种子延拓到目标振幅，一族多轨道叠加显示。
- 稳定性分析：Floquet 乘子 / 稳定性指数（nu1/nu2/nu3/Broucke）/ 分岔分类，对话框展示 + JSON 落盘。

**可视化**

- 多轨道可视化：3D / XY / XZ / YZ 投影、地月与 L1-L5 标注、多轨道叠加。

需要脚本化工作流（CR3BP 轨道生成、转移搜索、星历修正、绘图）时，使用 [e2m2e CLI](https://github.com/cislunarspace/e2m2e)，详见 [Sphinx 文档](https://cislunarspace.github.io/e2m2e/)。

## 数据流与数据格式

四个工具遵循同一数据流：面板填参数（或右键选中轨道）-> 后台线程调用 e2m2e 计算 -> 结果落盘 `output/`。所有产物统一用 JSON + NPZ 双文件：JSON 存参数与标量统计，NPZ 存轨道数组。`<type>` 为轨道类型小写（dro/halo/nrho/...），`<ts>` 为 UTC 时间戳。

| 工具 | 输入 | 输出落盘 |
|------|------|----------|
| 轨道设计 | 轨道类型、振幅、相位、起始历元、维持时间、步长 | `output/<type>/<type>_<ts>.json` + `.npz` |
| 轨道保持 | 选中轨道的星历 + 控制参数 | `output/ephemeris/orbit_ephemeris_<ts>.json` + `.npz` |
| 轨道族生成 | 平动点、最大面外振幅、成员数 | `output/family/family_<ts>.json` + `.npz` |
| 稳定性分析 | 选中轨道的状态与时间序列 | `output/stability/<label>_stability_<ts>.json` |

各产物的 JSON 与 NPZ 字段：

- **轨道设计**：JSON 存轨道类型、起始历元、维持天数、质量比 mu、Jacobi 常数、收敛状态与迭代次数、初始状态；NPZ 存 `states` (n,6)、`times` (n,)，以及星历字段（UTC 拆分、GCRS 位置/速度、会合系位置、时间）。
- **轨道保持**：JSON 存失败样本数、总速度增量、机动次数；NPZ 存受控星历 `states` (n,6)、`times` (n,)、惯性位置 `position_km`、物理时间 `times_et`。
- **轨道族生成**：JSON 存平动点、成员数、质量比；NPZ 存一族成员 `states` (m,n,6)、`times` (m,n)、面外振幅 `z0s` (m,)。
- **稳定性分析**：仅 JSON，存单值矩阵、特征值、稳定性指数（nu1/nu2/nu3/Broucke）、分岔分类与数值误差。

## 文档

在线文档：<https://cislunarspace.github.io/transfer-orbit-design/zh/>

本地构建：

```bash
uv sync --extra docs
uv run sphinx-build -b html -D language=zh docs/source docs/build/html
```

## 测试与代码规范

```bash
uv run pytest tests/ -m "not spice"
uv run ruff check .
uv run pyright
```

## 贡献

1. Fork 本仓库
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 开启 Pull Request

## License

[Apache 2.0](LICENSE)
