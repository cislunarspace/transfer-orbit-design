# transfer-orbit-design - Cislunar Orbit Design GUI

[![Release](https://img.shields.io/github/v/release/cislunarspace/transfer-orbit-design?label=release)](https://github.com/cislunarspace/transfer-orbit-design/releases)
[![CI](https://img.shields.io/github/actions/workflow/status/cislunarspace/transfer-orbit-design/ci.yml?branch=master&label=CI)](https://github.com/cislunarspace/transfer-orbit-design/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.13%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)

**English** | [简体中文](README.zh-CN.md)

transfer-orbit-design is the GUI frontend of [e2m2e](https://github.com/cislunarspace/e2m2e). e2m2e provides the dynamics models, correctors, continuators and transfer algorithms for cislunar orbit design; this repository wraps them into a visual desktop application. Since v4.0.0 the GUI is a Tauri 2 application: a React frontend drives the interface, a Rust shell orchestrates processes, and e2m2e runs as a sidecar child process (stdio JSON lines + binary frames). The UI never touches algorithms, and no algorithm enters the UI.

## Installation

### Desktop application (Windows)

Download `transfer-orbit-design_<version>_x64-setup.exe` from [GitHub Releases](https://github.com/cislunarspace/transfer-orbit-design/releases) (NSIS installer; per-user install, no administrator rights needed). The installer bundles the e2m2e runtime (transfer-orbit-design-sidecar) and the full SPICE kernel set including planetary ephemerides — everything works out of the box. Linux AppImage / deb packages and auto-update are also available on the releases page.

### Development environment

Requires Python >= 3.13, Node.js >= 20 and a stable Rust toolchain; Python packages are managed with [uv](https://docs.astral.sh/uv/):

```bash
uv sync                        # Python deps (e2m2e[mcp]>=5.9.0 etc.)
npm ci --prefix frontend       # Frontend deps
npx --prefix frontend tauri dev     # Dev mode: Vite HMR + Rust shell spawns the sidecar
```

## SPICE Kernels

SPICE kernels ship with the repository via Git LFS (`kernels/` after cloning) and are bundled in the installers; pure CR3BP tools never touch them. Situations that still call for preparation (slim environments, bring-your-own data):

- **Automatic download**: `uv run python scripts/download_kernels.py`, which idempotently fetches everything into `kernels/`;
- **Manual download**: extract e2m2e's [`kernels-v1` release](https://github.com/cislunarspace/e2m2e/releases) into `kernels/` (relative to the sidecar working directory);
- **Bring your own**: point `$SPICE_KERNEL_DIR` at an existing kernel directory (highest priority).

Official source: [NASA NAIF](https://naif.jpl.nasa.gov/naif/data.html) (fallback).

## Quick Start

1. The left column opens on the Project tab; switch to the Catalog tab to load the whole orbit library, with a filter bar for family type, libration point, Jacobi and amplitude ranges, and tags.
2. The middle column is the tool panel: pick a tool from the dropdown (orbit family generation / orbit design / parameter sweep / station keeping / orbit propagation / transfer design / spacetime transform / spatiography boundaries); the parameter form is generated from the tool's JSON Schema. Click Run.
3. For family generation, pick a family (Halo / NRHO / Axial / Lissajous / SPO / LPO / Horseshoe / DRO); the panel shows the family-specific parameters (amplitude bounds, perilune height, phases, …). Other tools render their own forms.
4. Result trajectories appear on the canvas: drag to rotate, scroll to zoom; the Fit button recentres on the trajectory bounding box. Catalog records can be pinned into the pinned layer (multi-select overlay) alongside the result layer for comparison.
5. The language switcher at the top of the left column toggles between Chinese and English; once a model service is configured, the assistant sidebar on the right drives computations conversationally (see "AI Assistant").

## Capabilities

- **Tool panel**: eight tools are wired: orbit family generation, orbit design, parameter sweep, station keeping, orbit propagation, transfer design, spacetime transform, and spatiography boundaries (the cislunar partition reference layer). Stability analysis stays out for now (upstream e2m2e marks it as a placeholder with an empty-arg schema). Parameter forms are generated from each tool's JSON Schema (field pruning, ranges and defaults follow the e2m2e models) and run through the generic tool-execution channel (the Rust `run_tool` command) straight to the sidecar; errors are surfaced directly. A preflight check validates required fields and numeric ranges before submission, flagging problems inline. The transfer-design form shows and hides fields by transfer type; on LGA/WSB submission it converts the selected orbit artifact into synodic physical units and injects it as the target ephemeris.
- **AI assistant (LLM+MCP, ADRs 0022/0023)**: a collapsible, resizable assistant sidebar on the right. The model service is BYOK: configure an OpenAI-compatible base URL, model name and API key in the "AI Assistant" section of the settings dialog (cloud DeepSeek/Qwen/Kimi or local Ollama/LM Studio, one protocol covers both); the key lives only in the OS credential manager, never in the webview JS context. The assistant calls e2m2e tools over standard MCP through a separate `mcp-serve` process, which never blocks the `serve-stdio` channel used by canvas computations. Tool calls are confirmed by tier: read-only queries run directly, while computing or mutating tools first show a tool card for the user to confirm, edit or reject. Sessions persist across restarts, with multiple sessions switchable and resumable; the thinking level has three per-session tiers (off/standard/deep). Products the assistant triggers follow the same semantics as manual runs: the same orbit library, lineage and canvas overlay.
- **Orbit family generation**: eight families (the seven classic ones + DRO), periodic continuation or parameter sampling; member trajectories rendered one by one.
- **Catalog browsing**: products are stored automatically in the e2m2e orbit library (multi-dimensional catalog); filtered queries; records can be multi-selected for simultaneous plotting, annotated, noted and starred. Annotation, family-member promotion, package export and deletion all have UI entries.
- **Canvas**: a Three.js 3D view whose content is split into a result layer (the latest computation, replaced on each run) and a pinned layer (pinned catalog records, soft-capped at 5 with a hint). NASA-textured bodies at true radius ratio with Phong lighting and a day/night terminator; an XYZ axes-and-grid reference layer; and a cislunar partition layer (Rosengren Primer boundaries: Hill/SOI/Battin reference geometry). Trajectories are colored by Jacobi constant on the coolwarm ramp with a color bar, falling back to the color cycle when no value exists; the legend annotates each trajectory's data frame (synodic nondimensional / synodic km / geocentric-inertial km). A timeline plays or scrubs a time marker along trajectories, with maneuver events (departure/arrival pulses) shown as clickable chips; chart settings (line width, markers, axes and region toggles, background, grid range) persist, and webm animation export is built in.

## Data Flow and Artifacts

Canvas computations flow: parameter form → Rust command → e2m2e sidecar (JSON-line envelopes + binary frames, e2m2e ADR 0035) → product lands in the orbit library automatically → project tree / canvas fetch it via `catalog_query` / `catalog_get`. The AI assistant is a parallel second channel: the Rust agent loop → a separate `mcp-serve` process (standard MCP) calling the same tools, so read-only queries never block a long canvas computation (ADR 0023).

Products persist in the `catalog/` directory (repo root in development; the install directory for the packaged app). The library is the e2m2e catalog format (multi-dimensional classification, lineage pointers) and can be opened directly by e2m2e or other hosts; `output/` only keeps the legacy transfer partition and script workflows.

## Documentation

Online docs: <https://cislunarspace.github.io/transfer-orbit-design/en/>

Build locally:

```bash
uv sync --extra docs
uv run sphinx-build -b html -D language=en docs/source docs/build/html/en
```

## Tests and Code Standards

```bash
uv run pytest tests/ -m "not spice"     # Python domain layer
cargo test --manifest-path src-tauri/Cargo.toml   # Rust shell & sidecar protocol
npm --prefix frontend run test          # Frontend (vitest)
uv run ruff check . && uv run pyright   # Python static checks
```

## Contributing

1. Fork this repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

[Apache 2.0](LICENSE)