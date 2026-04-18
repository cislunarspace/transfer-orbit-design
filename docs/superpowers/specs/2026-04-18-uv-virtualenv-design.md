# UV 虚拟环境配置设计

## Overview

为 transfer-orbit-design 项目配置 uv 虚拟环境，完全替代 conda 管理 Python 环境。

## Architecture

- **Python**: 3.13 via `.python-version`
- **Package Manager**: uv（替代 pip + conda）
- **Dependencies**: 通过 `pyproject.toml` 管理，包含 e2m2e 作为 git dependency

## Changes

### 1. pyproject.toml

添加 e2m2e 作为 git dependency：

```toml
dependencies = [
    "numpy>=2.4.0",
    "scipy>=1.17.0",
    "matplotlib>=3.10.0",
    "tqdm>=4.66",
    "PyQt6>=6.6.0",
    "e2m2e @ git+https://github.com/cislunarspace/e2m2e.git",
]
```

移除 `[project.optional-dependencies]` 中的 dev → 合并入主 dependencies。

### 2. requirements.txt

删除文件（依赖已迁移至 pyproject.toml）。

### 3. .python-version

创建文件，内容：`3.13`

### 4. CLAUDE.md

更新 Setup 节：

```bash
uv sync                        # 创建环境 + 安装所有依赖
uv run python scripts/gui/main.py
```

移除 conda 相关命令。

## Workflow

```bash
uv sync              # 创建 .venv，安装所有依赖（包括 e2m2e）
uv run <script>      # 在虚拟环境中运行脚本
```

## Notes

- e2m2e 安装自 GitHub，每次 `uv sync` 会检查最新 commit
- 如果需要固定版本，可指定 `@v4.0.0` 或 `@main` branch
