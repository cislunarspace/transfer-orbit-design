# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring the codebase.

This is a **multi-context** repo. Read `CONTEXT-MAP.md` at the repo root first — it points at one `CONTEXT.md` per context.

## Before exploring, read these

- **`CONTEXT-MAP.md`** at the repo root — read this first to understand which contexts exist and where they live.
- **Per-context `CONTEXT.md`** files — read each one relevant to the topic you're about to work on.
- **`docs/adr/`** — read ADRs that touch the area you're about to work in. Also check `src/<context>/docs/adr/` for context-scoped decisions.

If any of these files don't exist, **proceed silently**. Don't flag their absence; don't suggest creating them upfront. The producer skill (`/grill-with-docs`) creates them lazily when terms or decisions actually get resolved.

## File structure

```
/
├── CONTEXT-MAP.md                     ← maps context names to their directories
├── docs/adr/                          ← system-wide decisions
└── src/
    ├── <context-a>/
    │   ├── CONTEXT.md
    │   └── docs/adr/                  ← context-specific decisions
    └── <context-b>/
        ├── CONTEXT.md
        └── docs/adr/
```

## Use the glossary's vocabulary

When your output names a domain concept (in an issue title, a refactor proposal, a hypothesis, a test name), use the term as defined in the relevant `CONTEXT.md`. Don't drift to synonyms the glossary explicitly avoids.

If the concept you need isn't in the glossary yet, that's a signal — either you're inventing language the project doesn't use (reconsider) or there's a real gap (note it for `/grill-with-docs`).

## Flag ADR conflicts

If your output contradicts an existing ADR, surface it explicitly rather than silently overriding:

> _Contradicts ADR-0007 (event-sourced orders) — but worth reopening because…_
