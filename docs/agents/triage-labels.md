# Triage Labels

Five labels drive the triage state machine. They must exist in the GitHub repository; if missing, create them via `gh label create`.

| Label | Role | Meaning |
|-------|------|---------|
| `needs-triage` | Entry | Maintainer needs to evaluate this issue |
| `needs-info` | Blocked | Waiting on the reporter for more information |
| `ready-for-agent` | Ready (agent) | Fully specified; an AFK agent can pick it up with no additional human context |
| `ready-for-human` | Ready (human) | Needs human implementation |
| `wontfix` | Closed | Will not be actioned |

## State machine

```
[New issue] → needs-triage
needs-triage → needs-info        (reporter must clarify)
needs-triage → ready-for-agent   (fully specified, AFK-ready)
needs-triage → ready-for-human   (needs human hands)
needs-triage → wontfix           (out of scope / rejected)
needs-info → needs-triage        (reporter responded, re-evaluate)
needs-info → wontfix             (no response after reasonable time)
ready-for-agent → (issue closed) (agent completed the work)
ready-for-human → (issue closed) (human completed the work)
```

## Label colours (suggested)

| Label | Colour |
|-------|--------|
| `needs-triage` | `#fbca04` (yellow) |
| `needs-info` | `#006b75` (teal) |
| `ready-for-agent` | `#0e8a16` (green) |
| `ready-for-human` | `#1d76db` (blue) |
| `wontfix` | `#b60205` (red) |
