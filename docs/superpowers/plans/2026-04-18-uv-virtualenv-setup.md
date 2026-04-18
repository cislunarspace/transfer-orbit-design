# UV Virtualenv Setup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Configure uv virtual environment for transfer-orbit-design project, replacing conda.

**Architecture:** Add e2m2e as git dependency in pyproject.toml, create .python-version, remove requirements.txt, update CLAUDE.md.

**Tech Stack:** uv, Python 3.13

---

## Task 1: Update pyproject.toml — add e2m2e dependency and PyQt6

**Files:**
- Modify: `pyproject.toml:22-27`

- [ ] **Step 1: Edit pyproject.toml dependencies**

Replace lines 22-27:
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

- [ ] **Step 2: Remove dev optional-dependencies (merge into main)**

Remove lines 32-33:
```toml
[project.optional-dependencies]
dev = ["pytest>=7.0"]
```

Merge pytest into main dependencies:
```toml
dependencies = [
    "numpy>=2.4.0",
    "scipy>=1.17.0",
    "matplotlib>=3.10.0",
    "tqdm>=4.66",
    "PyQt6>=6.6.0",
    "pytest>=7.0",
    "e2m2e @ git+https://github.com/cislunarspace/e2m2e.git",
]
```

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml && git commit -m "refactor: add e2m2e and PyQt6 to pyproject.toml, remove requirements.txt"
```

---

## Task 2: Delete requirements.txt

**Files:**
- Delete: `requirements.txt`

- [ ] **Step 1: Delete requirements.txt**

```bash
rm requirements.txt
```

- [ ] **Step 2: Commit**

```bash
git add requirements.txt && git rm requirements.txt && git commit -m "refactor: remove requirements.txt (deps now in pyproject.toml)"
```

---

## Task 3: Create .python-version

**Files:**
- Create: `.python-version`

- [ ] **Step 1: Create .python-version with content "3.13"**

```bash
echo "3.13" > .python-version
```

- [ ] **Step 2: Commit**

```bash
git add .python-version && git commit -m "chore: add .python-version for uv"
```

---

## Task 4: Update CLAUDE.md Setup section

**Files:**
- Modify: `CLAUDE.md:1-20` (Setup section)

- [ ] **Step 1: Replace Setup section**

Replace the Setup section (lines ~1-20) with:

```bash
## Setup

```bash
uv sync                        # 创建环境 + 安装所有依赖
uv run python scripts/gui/main.py
```
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md && git commit -m "docs: update CLAUDE.md for uv workflow"
```

---

## Task 5: Verify uv sync works

- [ ] **Step 1: Run uv sync**

```bash
uv sync
```

Expected: Creates `.venv/` and installs all dependencies including e2m2e.

- [ ] **Step 2: Verify e2m2e is importable**

```bash
uv run python -c "import e2m2e; print(e2m2e.__version__)"
```

Expected: Prints `4.0.0` or similar version.
