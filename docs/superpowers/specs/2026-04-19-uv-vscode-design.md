# VSCode uv 虚拟环境配置设计

## 概述

将项目 VSCode 配置从 Conda 迁移到 uv 本地虚拟环境（`.venv/`）。

## 改动文件

### 1. `.vscode/settings.json`

**改动点：**
- `python.defaultInterpreterPath` → `${workspaceFolder}/.venv/Scripts/python.exe`
- `python.analysis.pythonPath` → `${workspaceFolder}/.venv/Scripts/python.exe`
- `python.envManager` → `uv`
- `extraPaths` 路径改为 `${workspaceFolder}/../e2m2e`（相对路径，跨平台）
- 移除 `python-envs.defaultEnvManager` 和 `python-envs.defaultPackageManager`（不再需要 MS Python 扩展管理 conda）
- 保留 `python.terminal.activateEnvironment: false`（uv 通过命令行激活）

**完整配置：**
```json
{
    "python.defaultInterpreterPath": "${workspaceFolder}/.venv/Scripts/python.exe",
    "python.analysis.pythonPath": "${workspaceFolder}/.venv/Scripts/python.exe",
    "python.terminal.activateEnvironment": false,
    "python.envManager": "uv",
    "python.analysis.extraPaths": [
        "${workspaceFolder}/../e2m2e"
    ],
    "cursorpyright.analysis.extraPaths": [
        "${workspaceFolder}/../e2m2e"
    ],
    "python.testing.pytestArgs": [
        "tests"
    ],
    "python.testing.unittestEnabled": false,
    "python.testing.pytestEnabled": true
}
```

### 2. `.vscode/launch.json`

**改动点：**
将 3 个调试配置的 `python` 路径统一从硬编码的 Conda 路径改为：
```
${workspaceFolder}/.venv/Scripts/python.exe
```

**改动前：**
```json
"python": "C:\\Users\\ouyan\\miniconda3\\envs\\orbit-py313\\python.exe"
```

**改动后：**
```json
"python": "${workspaceFolder}/.venv/Scripts/python.exe"
```

同时移除各配置中的 `env.CONDA_DEFAULT_ENV` 字段。

## 用户操作

1. 创建虚拟环境：
   ```bash
   uv venv .venv
   ```

2. 安装依赖（如尚未）：
   ```bash
   uv sync
   ```

3. 如需在 VSCode 中调试，确认 VSCode 右下角解释器已选择 `.venv/Scripts/python.exe`

## 验证

- VSCode 打开项目时，Python 扩展应自动检测到 `.venv` 中的解释器
- 运行 `uv run python -m tod.pipelines.gui.main` 应正常启动 GUI
- `uv run pytest tests/` 应正常执行测试
- 调试（按 F5）应正常工作
