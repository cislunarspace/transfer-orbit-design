---
sidebar_position: 2
---

# 安装

## 依赖安装

```bash
uv sync
```

`uv sync` 会安装所有 Python 依赖，包括 e2m2e（来自 PyPI）和本项目的可编辑安装。

## 快速启动 GUI

```bash
uv run python -m tod.gui.main
```

## 环境要求

- Python ≥ 3.10
- Linux / macOS / Windows

## SPICE 内核（星历修正用）

星历修正脚本需要 SPICE 内核文件：

- `de440.bsp` — 星历数据
- `naif0012.tls` — 闰秒文件

放置于 `e2m2e/kernels/` 目录，或设置 `SPICE_KERNEL_DIR` 环境变量指向所在目录。
