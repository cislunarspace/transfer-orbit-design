# Domain Docs

**Layout:** Single-context

## Locations

| Document | Path | Purpose |
|----------|------|---------|
| Context | `CONTEXT.md` (repo root) | Domain language, terminology, and relationships for the entire project |
| ADRs | `docs/adr/` | Architectural Decision Records, numbered (`NNNN-slug.md`) |

## Consumer rules

1. **Read `CONTEXT.md`** before any architecture, refactoring, or diagnostic task. It defines the domain language — use its terms verbatim.
2. **Check `docs/adr/`** for relevant past decisions before proposing architectural changes. Reference existing ADRs when they apply.
3. **When writing new ADRs**, follow the numbering scheme (`NNNN-short-slug.md`) and cross-reference `CONTEXT.md` terms.
4. **When `CONTEXT.md` terminology is insufficient** (new domain concept, ambiguity found), flag it and propose an update.

## No multi-context

This is a single-context repo. There is no `CONTEXT-MAP.md`. All domain language is unified under one `CONTEXT.md`.
