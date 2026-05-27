---
name: git-commit
description: Stage and commit only the files modified in the current Reasonix session. Use when user says "git commit", "commit", or asks to commit changes.
---

# Git Commit

Full workflow: read session log → check for out-of-session changes → stage → write commit message → verify → commit.

**Core rule**: Only commit files tracked in the session log for the current Reasonix session. Other dirty files are out of scope unless the user explicitly includes them.

## Workflow

### 1. Read session log

Run this command to extract the current session's tracked files and clean up stale entries:

```bash
node -e "
const fs = require('fs');
const path = require('path');
const logPath = path.join(process.cwd(), '.reasonix', 'session-files.log');
if (!fs.existsSync(logPath)) { console.log('NO_LOG'); process.exit(0); }
const lines = fs.readFileSync(logPath, 'utf8').split('\n').filter(Boolean);
const now = Math.floor(Date.now() / 1000);
const staleCutoff = now - 86400; // 24h
const markers = new Map();
// First pass: find the most recent session marker
for (const line of lines) {
  const parts = line.split('\t');
  if (parts.length < 3) continue;
  const [marker, tsStr] = parts;
  const ts = parseInt(tsStr);
  if (isNaN(ts)) continue;
  if (!markers.has(marker) || markers.get(marker) < ts) {
    markers.set(marker, ts);
  }
}
// Find the most recently active session marker
let sessionMarker = null;
let latestTs = 0;
const staleMarkers = new Set();
for (const [marker, ts] of markers) {
  if (ts > latestTs) {
    if (sessionMarker && latestTs < staleCutoff) staleMarkers.add(sessionMarker);
    latestTs = ts;
    sessionMarker = marker;
  } else if (ts < staleCutoff) {
    staleMarkers.add(marker);
  }
}
if (!sessionMarker) { console.log('EMPTY'); process.exit(0); }
// Second pass: collect files for this session, clean stale
const myFiles = new Set();
const keep = [];
for (const line of lines) {
  const parts = line.split('\t');
  if (parts.length < 3) continue;
  const [marker, tsStr, ...rest] = parts;
  const filePath = rest.join('\t');
  const ts = parseInt(tsStr);
  if (staleMarkers.has(marker) || (isNaN(ts) ? false : ts < staleCutoff && marker !== sessionMarker)) continue;
  keep.push(line);
  if (marker === sessionMarker) myFiles.add(filePath);
}
fs.writeFileSync(logPath, keep.join('\n') + (keep.length ? '\n' : ''));
if (myFiles.size === 0) { console.log('EMPTY'); process.exit(0); }
console.log(JSON.stringify([...myFiles], null, 2));
"
```

Result interpretation:
- `NO_LOG` → session log doesn't exist. Fall back to conversation history (step 1b).
- `EMPTY` → no files tracked for this session. Ask user what to commit.
- JSON array → these are your SESSION_FILES.

### 1b. Fallback: infer from conversation history

If `NO_LOG` or `EMPTY`:
1. If there ARE dirty files (`git diff --name-only` shows something), warn: "Session file tracking didn't capture any files. Falling back to all dirty files."
2. Use `git diff --name-only` output as SESSION_FILES.

### 2. Check for out-of-session dirty files

Run `git diff --name-only` and `git diff --name-only --cached` to see all dirty/staged files. Compare with SESSION_FILES.

If there are dirty files NOT in SESSION_FILES:
- List them: "These files are also modified but were not tracked in this session:"
- Ask: "Include any of these in this commit?"
- Only add user-selected files to SESSION_FILES.

If ALL dirty files are in SESSION_FILES, proceed silently.

### 3. Inspect changes, scoped to SESSION_FILES

```
git diff --stat -- <SESSION_FILES>
git diff --cached --stat -- <SESSION_FILES>
```

Read `git diff -- <SESSION_FILES>` to understand what changed and why.

Check for:
- Which session files changed (new, modified, deleted)
- Magnitude of change
- Whether tests exist/pass for the changed code

### 4. Draft the commit message

Format:
```
<type>: <description>

<optional body>
```

**Types**: `feat` `fix` `refactor` `docs` `test` `chore` `perf` `ci`

**Rules**:
- First line ≤ 72 chars, starts with lowercase, no trailing period
- Body explains **why**, not what (the diff shows what)
- Good: `fix: correct unit constant in halo orbit plot`
- Bad: `update code`

### 5. Present to user before committing

Show:
1. Files to be staged (SESSION_FILES)
2. Proposed commit message

Wait for user confirmation. Do not commit without explicit approval.

### 6. Stage and commit

```bash
git add <SESSION_FILES>
git commit -m "type: description"
```

### 7. Verify

```bash
git status -- <SESSION_FILES>
git log --oneline -3
```

Session files should be clean. Do not report other dirty files.

## How to pick the type

| Change | Type |
|--------|------|
| New feature | `feat` |
| Bug fix | `fix` |
| Code restructure (same behavior) | `refactor` |
| Documentation only | `docs` |
| Test only | `test` |
| CI/CD config | `ci` |
| Dependency/package change | `chore` |
| Performance improvement | `perf` |

## How to pick what to stage

**Source of truth = `.reasonix/session-files.log` filtered by the most recent session marker.**

- Never `git add -A`, `git add .`, or bare `git add` without explicit paths
- Stage each file explicitly by path
- Pre-existing dirty files are invisible unless user explicitly includes them

## When to split commits

Split when session files contain independent concerns:
- Refactor + new feature + fix mixed together
- CI/config changes alongside logic changes
- Partial refactor worth landing incrementally

Do not split artificially if changes are genuinely atomic.

## Edge cases

- **No session files changed**: Do not commit. Tell the user nothing was modified.
- **Session files conflict with merge state**: Do not commit. Resolve first.
- **Large diff (>20 files)**: Confirm with user — one commit or split.
- **New untracked file in log**: Include automatically.
- **Dirty files outside session**: Ask user via step 2.
- **Log file missing**: Fall back to all dirty files with warning.
