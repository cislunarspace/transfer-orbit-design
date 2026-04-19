# VSCode FiraCode Nerd Font 配置实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 VSCode 编辑器字体设置为 FiraCode Nerd Font，启用连字，字号 14。

**Architecture:** 在 `.vscode/settings.json` 中新增 3 行字体配置。

**Tech Stack:** VSCode JSON 配置

---

## 改动文件

- Modify: `.vscode/settings.json`

---

### Task 1: 添加字体配置到 settings.json

**Files:**
- Modify: `.vscode/settings.json`

- [ ] **Step 1: 添加字体配置**

在 `settings.json` 末尾（最后一行 `}` 之前）新增 3 行：

```json
    "editor.fontFamily": "FiraCode Nerd Font",
    "editor.fontSize": 14,
    "editor.fontLigatures": true
```

完整文件应为：

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

- [ ] **Step 2: 验证 JSON 格式正确**

运行: `python -c "import json; json.load(open('.vscode/settings.json'))"`
预期: 无输出（成功解析）

- [ ] **Step 3: 提交**

```bash
git add .vscode/settings.json
git commit -m "$(cat <<'EOF'
feat: set VSCode font to FiraCode Nerd Font with ligatures

- editor.fontFamily: FiraCode Nerd Font
- editor.fontSize: 14
- editor.fontLigatures: true

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Spec 覆盖检查

| Spec 要求 | Task |
|-----------|------|
| fontFamily: FiraCode Nerd Font | Task 1 |
| fontSize: 14 | Task 1 |
| fontLigatures: true | Task 1 |

无遗漏。
