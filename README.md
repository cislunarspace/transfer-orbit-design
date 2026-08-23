# transfer-orbit-design - 地月空间轨道设计 GUI

[![Release](https://img.shields.io/github/v/release/cislunarspace/transfer-orbit-design?label=release)](https://github.com/cislunarspace/transfer-orbit-design/releases)
[![CI](https://img.shields.io/github/actions/workflow/status/cislunarspace/transfer-orbit-design/ci.yml?branch=master&label=CI)](https://github.com/cislunarspace/transfer-orbit-design/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.13%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)

中文 | [English](README.en.md)

transfer-orbit-design 是 [e2m2e](https://github.com/cislunarspace/e2m2e) 的 GUI 前端。e2m2e 提供地月空间轨道设计所需的动力学模型、修正器、延拓器与转移算法，本仓库把它们封装成可视化桌面应用。v4.0.0 起 GUI 为 Tauri 2 架构：React 前端负责界面，Rust 壳负责进程编排，e2m2e 以 sidecar 子进程运行（stdio JSON 行 + 二进制帧协议）：界面不碰算法，算法不进界面。

## 安装

### 桌面应用（Windows）

从 [GitHub Releases](https://github.com/cislunarspace/transfer-orbit-design/releases) 下载 `tod_<版本>_x64-setup.exe`（NSIS 安装器，免管理员权限，安装到当前用户目录）。安装包内含 e2m2e 运行时（tod-sidecar）与 SPICE 小内核；纯 CR3BP 工具（轨道族生成、任务轨道设计）无需额外准备，星历类工具（转移设计、轨道预报等）还需行星历 `.bsp` 内核（见下节）。

### 开发环境

要求 Python >= 3.13、Node.js >= 20、Rust 稳定版工具链，包管理用 [uv](https://docs.astral.sh/uv/)：

```bash
uv sync                        # Python 依赖（e2m2e>=5.8.5 等）
npm ci --prefix frontend       # 前端依赖
cargo tauri dev                # 开发模式启动：Vite 热更新 + Rust 壳拉起 sidecar
```

## SPICE 内核

纯 CR3BP 工具（轨道族生成、任务轨道设计）不需要 SPICE 内核；转移设计、轨道预报、时空坐标转换等星历工具需要行星历 `.bsp` 等内核，获取方式：

- **自动下载（推荐）**：`uv run python scripts/download_kernels.py`，幂等拉取到 `kernels/`；
- **手动下载**：从 e2m2e 的 [`kernels-v1` release](https://github.com/cislunarspace/e2m2e/releases) 解压到 `kernels/`（sidecar 工作目录下的相对路径）；
- **自备数据**：`$SPICE_KERNEL_DIR` 指向已有内核目录（优先级最高）。

官方来源：[NASA NAIF](https://naif.jpl.nasa.gov/naif/data.html)（备用）。

## 快速开始

1. 启动后左栏默认项目页签；切到轨道库页签自动加载全库，过滤栏可按族类型、平动点、Jacobi 与振幅区间、标签组合筛选。
2. 中栏工具面板：下拉选择工具（轨道族生成 / 任务轨道设计 / 轨道保持 / 轨道预报 / 转移轨道设计 / 轨道稳定性 / 时空坐标转换），参数表单按工具的 JSON Schema 自动生成，点执行。
3. 轨道族生成选族类型（Halo / NRHO / Axial / Lissajous / SPO / LPO / Horseshoe / DRO），按族显示对应参数（振幅上下限、近月点高度、相位等）；其余工具各自渲染参数表单。
4. 结果轨迹随即出现在右侧画布：左键拖拽旋转、滚轮缩放；适配按钮按轨迹包围盒复位视角。点击轨道库记录可把库轨迹叠加到画布。
5. 左栏右上角语言切换中英界面。

## 能力

**v4.0.0 界面可用**

- **工具面板**：七个工具全部接入：轨道族生成、任务轨道设计、轨道保持、轨道预报、转移轨道设计、轨道稳定性、时空坐标转换。参数表单由各工具的 JSON Schema 自动生成（字段裁剪、范围与默认值随 e2m2e 模型走），经通用工具执行通道（Rust `run_tool` 命令）直达 sidecar，错误直显。
- **轨道族生成**：八族（七族 + DRO）周期延拓/参数采样，成员轨迹逐条渲染。
- **轨道库浏览**：产物自动入 e2m2e 轨道库（catalog 多维分类），多维过滤查询，选中记录叠加画布。
- **画布**：Three.js 3D 视图，视图适配与视图保持、地月与平动点标注、图表设置（线宽/天体与平动点标注/Z 轴比例）持久化、webm 动画导出。

## 数据流与产物

一次计算的数据流：参数表单 → Rust 命令 → e2m2e sidecar（JSON 行信封 + 二进制帧，e2m2e ADR 0035）→ 产物自动入轨道库 → 项目树/画布经 `catalog_query` / `catalog_get` 取用。

产物持久化在 `catalog/` 目录（开发期仓库根 `catalog/`；安装版在安装目录下）。轨道库是 e2m2e catalog 格式（多维分类、谱系指针），可以直接被 e2m2e 或其他宿主打开；`output/` 仅保留转移遗留分区与脚本场景。

## 文档

在线文档：<https://cislunarspace.github.io/transfer-orbit-design/zh/>

本地构建：

```bash
uv sync --extra docs
uv run sphinx-build -b html -D language=zh docs/source docs/build/html
```

## 测试与代码规范

```bash
uv run pytest tests/ -m "not spice"     # Python 领域层
cargo test --manifest-path src-tauri/Cargo.toml   # Rust 壳与 sidecar 协议
npm --prefix frontend run test          # 前端（vitest）
uv run ruff check . && uv run pyright   # Python 静态检查
```

## 贡献

1. Fork 本仓库
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 开启 Pull Request

## License

[Apache 2.0](LICENSE)