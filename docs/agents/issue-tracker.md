# Issue 跟踪

**系统：** GitHub Issues

**远端：** `https://github.com/cislunarspace/transfer-orbit-design`

**CLI：** `gh`（GitHub CLI）

## 命令

| 操作 | 命令 |
|--------|---------|
| 创建 issue | `gh issue create --title "..." --body "..."` |
| 列出 issue | `gh issue list` |
| 查看 issue | `gh issue view <number>` |
| 关闭 issue | `gh issue close <number>` |
| 添加标签 | `gh issue edit <number> --add-label "..."` |
| 移除标签 | `gh issue edit <number> --remove-label "..."` |
| 评论 | `gh issue comment <number> --body "..."` |

## 约定

- 适用时在 issue 标题中使用约定式提交前缀（feat:、fix:、refactor: 等）。
- 创建或更新 issue 时，总要打上一个 triage 标签。
- 在提交中用 `Fixes #<number>` 或 `Closes #<number>` 引用 issue。
