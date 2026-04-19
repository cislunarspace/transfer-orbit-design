# VSCode FiraCode Nerd Font 配置设计

## 概述

将 VSCode 编辑器字体设置为 FiraCode Nerd Font，并启用连字特性。

## 改动文件

### `.vscode/settings.json`

在现有配置基础上新增 3 项：

| 设置 | 值 | 说明 |
|------|-----|------|
| `editor.fontFamily` | `"FiraCode Nerd Font"` | 字体族 |
| `editor.fontSize` | `14` | 字号 |
| `editor.fontLigatures` | `true` | 启用连字 |

### 完整配置

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
    "python.testing.pytestEnabled": true,
    "editor.fontFamily": "FiraCode Nerd Font",
    "editor.fontSize": 14,
    "editor.fontLigatures": true
}
```

## 前提条件

用户需先安装 [FiraCode Nerd Font](https://github.com/ryanoasis/nerd-fonts/releases) 并在系统字体目录中可用。

## 验证

- VSCode 重载窗口后，编辑器字体应显示为 FiraCode Nerd Font
- `->`、`!=`、`=>` 等连字应正常显示
