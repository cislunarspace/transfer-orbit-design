# transfer-orbit-design - Cislunar Orbit Design GUI

[![Release](https://img.shields.io/github/v/release/cislunarspace/transfer-orbit-design?label=release)](https://github.com/cislunarspace/transfer-orbit-design/releases)
[![CI](https://img.shields.io/github/actions/workflow/status/cislunarspace/transfer-orbit-design/ci.yml?branch=master&label=CI)](https://github.com/cislunarspace/transfer-orbit-design/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.13%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)

[中文](README.md) | English

transfer-orbit-design is the GUI frontend of [e2m2e](https://github.com/cislunarspace/e2m2e). e2m2e provides the dynamics models, correctors, continuators and transfer algorithms for cislunar orbit design; this repository wraps them into a visual desktop application. Since v4.0.0 the GUI is a Tauri 2 application: a React frontend drives the interface, a Rust shell orchestrates processes, and e2m2e runs as a sidecar child process (stdio JSON lines + binary frames). The UI never touches algorithms, and no algorithm enters the UI.

## Installation

### Desktop application (Windows)

Download `tod_<version>_x64-setup.exe` from [GitHub Releases](https://github.com/cislunarspace/transfer-orbit-design/releases) (NSIS installer; per-user install, no administrator rights needed). The installer bundles the e2m2e runtime (tod-sidecar) and the small SPICE kernels; pure CR3BP tools (orbit family generation, orbit design) need no extra kernels, while ephemeris-based tools (transfer design, propagation, …) need the planetary ephemeris `.bsp` (see below).

### Development environment

Requires Python >= 3.13, Node.js >= 20 and a stable Rust toolchain; Python packages are managed with [uv](https://docs.astral.sh/uv/):

```bash
uv sync                        # Python deps (e2m2e>=5.8.5 etc.)
npm ci --prefix frontend       # Frontend deps
cargo tauri dev                # Dev mode: Vite HMR + Rust shell spawns the sidecar
```

## SPICE Kernels

Pure CR3BP tools (orbit family generation, orbit design) need no SPICE kernels; ephemeris-based tools (transfer design, orbit propagation, spacetime transform) need the planetary ephemeris `.bsp` and friends, obtainable via:

- **Automatic download (recommended)**: `uv run python scripts/download_kernels.py` — idempotently fetches everything into `kernels/`;
- **Manual download**: extract e2m2e's [`kernels-v1` release](https://github.com/cislunarspace/e2m2e/releases) into `kernels/` (relative to the sidecar working directory);
- **Bring your own**: point `$SPICE_KERNEL_DIR` at an existing kernel directory (highest priority).

Official source: [NASA NAIF](https://naif.jpl.nasa.gov/naif/data.html) (fallback).

## Quick Start

1. The left column opens on the "Project" tab; switch to the "Catalog" tab to load the whole orbit library, with a filter bar for family type, libration point, Jacobi and amplitude ranges, and tags.
2. The middle column is the tool panel: pick a tool from the dropdown (orbit family generation / orbit design / station keeping / orbit propagation / transfer design / stability analysis / spacetime transform); the parameter form is generated from the tool's JSON Schema. Click "Run".
3. For family generation, pick a family (Halo / NRHO / Axial / Lissajous / SPO / LPO / Horseshoe / DRO); the panel shows the family-specific parameters (amplitude bounds, perilune height, phases, …). Other tools render their own forms.
4. Result trajectories appear on the canvas: drag to rotate, scroll to zoom; the "Fit" button recentres on the trajectory bounding box. Clicking a catalog record overlays its trajectories on the canvas.
5. The language switcher at the top of the left column toggles between Chinese and English.

## Capabilities

**Available in the v4.0.0 UI**

- **Tool panel**: all seven tools are wired — orbit family generation, orbit design, station keeping, orbit propagation, transfer design, stability analysis, spacetime transform. Parameter forms are generated from each tool's JSON Schema (field pruning, ranges and defaults follow the e2m2e models) and run through the generic tool-execution channel (the Rust `run_tool` command) straight to the sidecar; errors are surfaced directly.
- **Orbit family generation**: eight families (the seven classic ones + DRO), periodic continuation or parameter sampling; member trajectories rendered one by one.
- **Catalog browsing**: products are stored automatically in the e2m2e orbit library (multi-dimensional catalog); filtered queries; clicking a record overlays it on the canvas.
- **Canvas**: Three.js 3D view with view-fit and view-preservation, Earth/Moon and libration-point annotations, persisted chart settings (line width, body/point markers, Z-axis ratio), webm animation export. Tool result trajectories render adaptively from the response structure (JSON `states`/`position_km`/`trajectory` arrays or binary frames), with no per-tool canvas code.

## Data Flow and Artifacts

One computation flows: parameter form → Rust command → e2m2e sidecar (JSON-line envelopes + binary frames, e2m2e ADR 0035) → product lands in the orbit library automatically → project tree / canvas fetch it via `catalog_query` / `catalog_get`.

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
