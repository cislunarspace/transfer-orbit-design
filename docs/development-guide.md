# 开发指南

## e2m2e 依赖管理

本项目依赖 e2m2e 库（地月空间转移轨道设计）。推荐使用 `pip install -e` 可编辑安装，使 `from e2m2e.core...` 导入在任意工作目录下均可正确解析。

### 安装方式

```bash
# 克隆 e2m2e 仓库
git clone <e2m2e-repository-url> /path/to/e2m2e

# 以可编辑模式安装
pip install -e /path/to/e2m2e
```

`requirements.txt` 末尾的 `-e .` 会把本仓库（transfer-orbit-design）也以可编辑包形式安装，使 `from scripts.utils...` 等导入无需额外配置 `PYTHONPATH`。

### IDE 配置（Cursor / VS Code）

Pylance 语言服务器需正确找到 `e2m2e`，在 `pyproject.toml` 中已配置：

```toml
[tool.pyright]
extraPaths = ["../e2m2e"]
pythonVersion = "3.13"
```

根据 e2m2e 实际位置调整 `extraPaths`。

### 工作流程

1. **修改 e2m2e**：直接在 e2m2e 源码目录中编辑代码
2. **git 管理**：在 e2m2e 仓库中进行版本控制
3. **运行脚本**：`python scripts/dro/generate_dro_family.py`，改动实时生效
