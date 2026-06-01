# Issue Tracker

**System:** GitHub Issues

**Remote:** `https://github.com/cislunarspace/transfer-orbit-design`

**CLI:** `gh` (GitHub CLI)

## Commands

| Action | Command |
|--------|---------|
| Create issue | `gh issue create --title "..." --body "..."` |
| List issues | `gh issue list` |
| View issue | `gh issue view <number>` |
| Close issue | `gh issue close <number>` |
| Add label | `gh issue edit <number> --add-label "..."` |
| Remove label | `gh issue edit <number> --remove-label "..."` |
| Comment | `gh issue comment <number> --body "..."` |

## Conventions

- Use conventional commit prefixes in issue titles when applicable (feat:, fix:, refactor:, etc.).
- Always assign a triage label when creating or updating an issue.
- Reference issues in commits with `Fixes #<number>` or `Closes #<number>`.
