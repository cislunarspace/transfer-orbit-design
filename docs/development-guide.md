# 开发指南

## e2m2e 依赖管理

本项目依赖 [e2m2e](https://github.com/cislunarspace/e2m2e) 库（地月空间转移轨道设计）。为方便开发和调试，采用**符号链接**方式将 `e2m2e` 源码引入项目。

### 目录结构

```
transfer-orbit-design/
├── e2m2e/  ──────────────────────→  ~/codes/e2m2e/e2m2e  (符号链接)
├── scripts/
│   └── transfer/
│       └── grid_search.py          from e2m2e.core.dynamics import ...
```

### 建立符号链接

首次 clone 后，运行以下命令建立链接：

```bash
# 在项目根目录下执行
ln -s /home/desktop/codes/e2m2e/e2m2e e2m2e
```

> 注意：`/home/desktop/codes` 为 e2m2e 源码的父目录路径，需根据实际情况调整。

### IDE 配置（Cursor / VS Code）

Pylance 语言服务器需正确找到 `e2m2e`，在 `pyproject.toml` 中配置：

```toml
[tool.pyright]
extraPaths = ["/home/desktop/codes/e2m2e"]
pythonVersion = "3.13"
```

### 工作流程

1. **修改 e2m2e**：直接在 `~/codes/e2m2e/e2m2e/` 中编辑代码
2. **git 管理**：在 `~/codes/e2m2e/` 中进行版本控制
3. **运行脚本**：`cd transfer-orbit-design && python scripts/transfer/grid_search.py`，改动实时生效

### 重新初始化

如果符号链接失效，重新创建：

```bash
cd /home/desktop/codes/transfer-orbit-design
rm -f e2m2e
ln -s /home/desktop/codes/e2m2e/e2m2e e2m2e
```
