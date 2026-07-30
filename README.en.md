# Transfer Orbit Design

[![Release](https://img.shields.io/github/v/release/cislunarspace/transfer-orbit-design?label=release)](https://github.com/cislunarspace/transfer-orbit-design/releases)
[![CI](https://img.shields.io/github/actions/workflow/status/cislunarspace/transfer-orbit-design/ci.yml?branch=master&label=CI)](https://github.com/cislunarspace/transfer-orbit-design/actions/workflows/ci.yml)
[![Stars](https://img.shields.io/github/stars/cislunarspace/transfer-orbit-design?style=flat)](https://github.com/cislunarspace/transfer-orbit-design/stargazers)
[![Issues](https://img.shields.io/github/issues/cislunarspace/transfer-orbit-design)](https://github.com/cislunarspace/transfer-orbit-design/issues)
[![Last commit](https://img.shields.io/github/last-commit/cislunarspace/transfer-orbit-design/master)](https://github.com/cislunarspace/transfer-orbit-design/commits/master)
[![Python](https://img.shields.io/badge/python-3.13%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)

[中文](README.md) | English

Transfer Orbit Design is a collection of scripts and GUI tools for cislunar orbit design. It provides CR3BP periodic orbit family generation, DRO↔RO/GEO/LEO transfer search and optimization, CR3BP-to-ephemeris-model correction, and supporting plotting tools with a graphical interface. This repository handles script orchestration, parameter management, result storage, and visualization; the dynamics, correctors, continuators, and transfer algorithms are provided by the sibling `e2m2e` repository.

> This tool serves three technical directions of cislunar development: **in-space mobility**, **in-space servicing**, and **cislunar technologies**. The current version focuses on fundamental orbit design capabilities for in-space mobility, and will expand toward the other two directions from this foundation. See [Mission and Roadmap](#mission-and-roadmap) for the background, capability mapping, and future plans.

## Feature Overview

| Category | Capabilities | Typical output |
|------|------|----------|
| CR3BP orbit generation | 4 periodic orbit families: DRO, DPO, Halo, RO | JSON/CSV under `output/<orbit-type>/` |
| Transfer search | DRO→RO, DRO→GEO, GEO→DRO, LEO→DRO grid search | `search_results_*.json` |
| Transfer optimization | NLP optimization on grid search results, minimizing two-impulse or insertion cost | `optimization_results_*.json` |
| Ephemeris conversion | Correct CR3BP DRO/Halo orbits or orbit families into the real ephemeris model | Corrected result JSON under `output/ephemeris/` |
| Plotting & inspection | Orbit family overview, stability maps, search/optimization plots, single-orbit inspector | Matplotlib windows or saved figures |
| Trajectory analysis | STM condition number, segmented shooting parameter sensitivity, CR3BP dataset statistics | Analysis JSON under `output/transfer/`, figures under `figures/` |
| GUI | Organizes scripts, parameters, output directories, and run logs; zh/en language switch | Desktop interface |

## Installation

### 1. Clone the e2m2e dependency

The core algorithms depend on `e2m2e`, which is configured in `pyproject.toml` as a local path dependency (`../e2m2e`). `uv sync` will not fetch it from a remote, so clone it manually into the directory next to this repository:

```bash
cd ..
git clone https://github.com/cislunarspace/e2m2e.git
cd transfer-orbit-design
```

There is no need to install anything inside the e2m2e directory itself; the `uv sync` step below installs it in editable mode. See <https://cislunarspace.github.io/e2m2e/> for e2m2e's algorithm and force model details.

If you only want to use e2m2e without co-developing it, you can switch to the PyPI release instead: remove the `tool.uv.sources.e2m2e` entry from `pyproject.toml`, then run `uv add e2m2e`.

### 2. Install this project

The project requires Python `>=3.13`, pinned to 3.13 via `.python-version`. From the repository root:

```bash
uv sync
```

`uv sync` does everything in one pass: provisions the Python 3.13 interpreter, creates the virtual environment, installs all PyPI dependencies, installs the core algorithm library from `../e2m2e` in editable mode, and installs this project in editable mode. If the two repositories are not siblings, first adjust the `tool.uv.sources.e2m2e` path in `pyproject.toml`.

The ephemeris conversion scripts also need SPICE kernels. The recommended source is the `kernels-v1` bundle from [cislunarspace/e2m2e Releases](https://github.com/cislunarspace/e2m2e/releases) (accessible from within China); extract it to `../e2m2e/kernels`. The [NAIF website](https://naif.jpl.nasa.gov/naif/data.html) remains a fallback source.

```bash
export SPICE_KERNEL_DIR=../e2m2e/kernels
# The directory should contain: de430.bsp, de440s.bsp, earth_latest_high_prec.bpc,
# SPICEEarthPredictedKernel.bpc, SPICELunaCurrentKernel.bpc,
# SPICELunaFrameKernel.tf, naif0011.tls, naif0012.tls, pck00010.tpc
```

**Packaged build (PyInstaller portable bundle)**: the `TransferOrbitDesign-windows.zip` from GitHub Releases needs no environment variables. Additionally download `spice-kernels.zip` from the [`spice-data-v1`](https://github.com/cislunarspace/transfer-orbit-design/releases/tag/spice-data-v1) release and extract it next to `TransferOrbitDesign.exe` (producing a `kernels/` subdirectory); the application detects it at startup. An explicitly set `SPICE_KERNEL_DIR` environment variable still takes precedence. That release also ships the full MICE toolkit (`spice-mice-windows.zip` / `spice-mice-linux.zip`) for full development with MATLAB and similar tools; it is not required to run this application.

## Quick Start

### GUI

```bash
uv run python -m tod.gui.main
```

The GUI organizes scripts under "Generate / Ephemeris Conversion / Transfer / Plotting" and displays parameters, help text, and output directories based on the registrations in `tod/scripting/`.

**Language switch**: the GUI supports `zh` (Chinese, default) and `en` (English). Edit the `"language"` entry in `gui_defaults.json` and restart for it to take effect; entries missing a translation fall back to Chinese.

### CLI

Generate baseline orbits first, then run transfer or plotting scripts. All commands run from the repository root.

```bash
# DRO / DPO / Halo / RO
uv run python -m tod.generates.cr3bp.dro.generate_dro_orbit
uv run python -m tod.generates.cr3bp.dro.generate_dro_orbit --jacobi 3.1
uv run python -m tod.generates.cr3bp.dro.generate_dro_orbit --seed-id earth-moon_dro:000001
uv run python -m tod.generates.cr3bp.dro.generate_dro_family
uv run python -m tod.generates.cr3bp.dpo.generate_dpo_orbit
uv run python -m tod.generates.cr3bp.dpo.generate_dpo_family
uv run python -m tod.generates.cr3bp.halo.generate_halo_family
uv run python -m tod.generates.cr3bp.ro.generate_ro_family

# Transfer: grid search first, then NLP optimization
uv run python -m tod.transfers.dro_to_ro.grid_search_dro_to_ro
uv run python -m tod.transfers.dro_to_ro.optimize_dro_to_ro

# Ephemeris correction example (single orbit, DRO and Halo supported)
uv run python -m tod.generates.ephemeris.correct_orbit_to_ephemeris \
  --input-file output/dro/dro_<timestamp>.json \
  --reference-epoch 2026-01-01T00:00:00 \
  --orbit-type dro

uv run python -m tod.generates.ephemeris.correct_orbit_to_ephemeris \
  --input-file output/halo/halo_family_<timestamp>.json \
  --reference-epoch 2026-01-01T00:00:00 \
  --orbit-type halo
```

Some transfer scripts still carry hard-coded input paths. Before running, check the default file paths near the top of the script or in `main()`, and point them at JSON files you have generated locally.

## Script Catalog

### Orbit Generation (CR3BP)

The single-orbit DRO entry point has been renamed from the old 3:1-specific script to `generate_dro_orbit`. The manual path still supports `--x0/--vy0/--period` with fixed-period differential correction; the catalog path selects a full 6-DOF seed from `data/cr3bp_data/normalized` via `--jacobi` or `--seed-id` and propagates it directly. If the normalized catalog is missing, the script builds it from `data/cr3bp_data/raw` by default; pass `--no-auto-build-catalog` to disable the automatic build. Single-orbit output is named `output/dro/dro_<timestamp>.json`; DRO family artifacts such as `dro_31_family_*` are unaffected by the single-orbit rename.

Each orbit family provides two scripts: **single-orbit generation** (fixed-period differential correction) and **family continuation** (natural continuation).

| Orbit family | Single-orbit script | Family script | Notes |
|--------|-----------|-----------|------|
| DRO | `tod.generates.cr3bp.dro.generate_dro_orbit` | `tod.generates.cr3bp.dro.generate_dro_family` | Distant retrograde orbit around the secondary |
| DPO | `tod.generates.cr3bp.dpo.generate_dpo_orbit` | `tod.generates.cr3bp.dpo.generate_dpo_family` | Distant prograde orbit around the secondary |
| Halo | `tod.generates.cr3bp.halo.generate_halo_orbit` | `tod.generates.cr3bp.halo.generate_halo_family` | 3D periodic orbits; natural and pseudo-arclength continuation |
| RO | `tod.generates.cr3bp.ro.generate_ro_orbit` | `tod.generates.cr3bp.ro.generate_ro_family` | Resonant orbits |

### Transfer Search and Optimization

| Direction | Search script | Optimization script | Notes |
|---------|---------|---------|------|
| DRO → RO | `tod.transfers.dro_to_ro.grid_search_dro_to_ro` | `tod.transfers.dro_to_ro.optimize_dro_to_ro` | Two-impulse candidate search + NLP optimization |
| DRO → GEO | `tod.transfers.dro_to_geo.grid_search_dro_to_geo` | `tod.transfers.dro_to_geo.optimize_dro_to_geo` | GEO spherical insertion window search + optimization |
| GEO → DRO | `tod.transfers.geo_to_dro.grid_search_geo_to_dro` | `tod.transfers.geo_to_dro.optimize_geo_to_dro` | Search + optimization from GEO to DRO |
| GEO → DRO | — | `tod.transfers.geo_to_dro.validate_geo_to_dro` | Validate GEO→DRO transfer results |
| LEO → DRO | `tod.transfers.leo_to_dro.grid_search_leo_to_dro` | `tod.transfers.leo_to_dro.optimize_leo_to_dro` | Search + optimization from LEO to DRO |

### Transfer Ephemeris Correction and Analysis

These scripts handle ephemeris correction and downstream numerical analysis for transfer trajectories such as DRO→GEO. All live under `tod/transfers/dro_to_geo/`.

| Script | Function |
|------|------|
| `tod.transfers.dro_to_geo.transfer_to_ephemeris` | CR3BP→J2000 coordinate conversion of the optimized trajectory with ephemeris propagation comparison (no correction) |
| `tod.transfers.dro_to_geo.correct_transfer_to_ephemeris` | Multiple-shooting ephemeris correction of transfer trajectories; supports standard/two_level/homotopy/segmented (segmented shooting with merging) |
| `tod.transfers.dro_to_geo.compare_low_thrust` | Fuel consumption comparison between low-thrust and impulsive transfers |
| `tod.transfers.dro_to_geo.analyze_stm_condition_number` | Segment-wise and cumulative STM condition number analysis along a corrected trajectory, assessing the numerical stability of shooting methods |
| `tod.transfers.dro_to_geo.analyze_patch_point_sensitivity` | Sensitivity analysis of the segmented-shooting `points_per_segment` parameter |
| `tod.transfers.dro_to_geo.analyze_cr3bp_dataset` | Statistics and coverage plots for the raw CR3BP XLSX dataset |

### Ephemeris Conversion

| Target | Single orbit | Orbit family | Notes |
|------|--------|--------|------|
| General | `tod.generates.ephemeris.correct_orbit_to_ephemeris` | — | Unified entry; supports DRO/Halo and multiple methods |
| DRO | — | `tod.generates.ephemeris.family_correction` (SCRIPT_ENTRIES[0]) | Multiple-shooting correction of an orbit family into the ephemeris model |
| Halo | — | `tod.generates.ephemeris.family_correction` (SCRIPT_ENTRIES[1]) | Multiple-shooting correction of an orbit family into the ephemeris model |

> `correct_orbit_to_ephemeris` selects the orbit type and correction method via `--orbit-type` (`dro`/`halo`) and `--method` (`standard`/`two_level`/`homotopy`). `--output-prefix` automatically produces `{prefix}_{method}_tol{tol}.json`. Output includes timing and geocentric distance statistics. The method defaults to `two_level`.

### Plotting

| Category | Script | Function |
|------|------|------|
| DRO | `tod.plot.dro.plot_dro_family` | DRO family overview |
| Halo | `tod.plot.halo.plot_halo_family` | Halo family 2D/3D views, with stride-based sampling |
| Ephemeris | `tod.plot.ephemeris.plot_ephemeris_correction` | Ephemeris correction comparison plots |
| Inspection | `tod.plot.inspection.plot_single_orbit` | Single-orbit inspector |
| Inspection | `tod.plot.inspection.plot_interactive_orbit_inspector` | Interactive orbit inspector |
| Transfer | `tod.plot.transfer.dro_to_ro.plot_search_results_dro_to_ro` | DRO→RO search result visualization |
| Transfer | `tod.plot.transfer.dro_to_ro.plot_optimize_result_dro_to_ro` | DRO→RO optimization result visualization |
| Transfer | `tod.plot.transfer.dro_to_geo.*` | DRO→GEO search/optimization visualization |
| Transfer | `tod.plot.transfer.geo_to_dro.*` | GEO→DRO search/optimization visualization |
| Transfer | `tod.plot.transfer.leo_to_dro.*` | LEO→DRO search/optimization visualization |

> The orbit family plotting scripts share a unified `FamilyPlotOrchestrator` architecture. The standalone plotting scripts of some older families (the RO series) have been merged into the orchestrator.

## Output Data

Orbit and transfer results are stored mainly as JSON. Common keys include:

- `states`: state history, usually non-dimensional `[x, y, z, vx, vy, vz]` in CR3BP.
- `times`: time array corresponding to the states.
- `period`: orbit period or propagation duration.
- `orbit_type`: orbit type identifier, e.g. `DRO`, `DPO`, `Halo`, `RO`.
- `metadata`: auxiliary information such as script configuration, continuation steps, and error statistics.

`output/*/family.json` is a convenience copy of the most recent generation and gets overwritten; use the timestamped file names for long-term references.

## Directory Structure

```text
tod/
  commons/        Constants, paths, and shared utilities
  generates/      CR3BP orbit generation and CR3BP→ephemeris conversion scripts
    cr3bp/          Per-family generation (dro, dpo, halo, ro)
    ephemeris/      DRO/Halo ephemeris conversion (single orbit and family)
  transfers/      DRO/RO/GEO/LEO transfer search and optimization scripts
  plot/           Plotting scripts for orbits, families, search and optimization results
  gui/            PyQt6 GUI: script registry, parameter panels, run management, themes, i18n
docs/
  source/         Sphinx documentation sources (including PRDs under narrative/)
  adr/            Architecture decision records
  development.md  Development and documentation conventions
output/           Result directory created on demand by script runs
```

## Mission and Roadmap

### Background

Transfer Orbit Design addresses the needs of cislunar development along three technical directions: **in-space mobility**, **in-space servicing**, and **cislunar technologies**. Its role is to provide a reproducible, extensible orbit design and analysis foundation for all three. The current version delivers core capabilities for in-space mobility; the other two directions advance according to the roadmap.

### 1. In-Space Mobility (Implemented)

The goal of this direction is to greatly improve orbit maneuver capability. The software's role is to **support** that goal with CR3BP low-energy orbit and transfer design, rather than to perform the maneuver itself — the latter is a mission-level engineering objective.

The implemented capabilities map to scripts in this repository:

- **Periodic orbit family generation**: 4 CR3BP periodic orbit families (DRO, DPO, Halo, RO), usable as departure/target orbits for transfer design. See [Orbit Generation (CR3BP)](#orbit-generation-cr3bp).
- **Transfer search and optimization**: two-impulse grid search and NLP optimization for DRO→RO, DRO→GEO, GEO→DRO, and LEO→DRO, minimizing Δv or insertion cost and providing candidate solutions for low-energy transfer design. See [Transfer Search and Optimization](#transfer-search-and-optimization).
- **Ephemeris correction**: multiple-shooting correction of CR3BP design results into the real ephemeris model, narrowing the gap between design and engineering implementation. See [Ephemeris Conversion](#ephemeris-conversion).

### 2. In-Space Servicing (Planned)

Target direction: on-orbit refueling, repair, and rapid replacement of spacecraft. Planned coverage:

- Trajectory design for rendezvous and proximity operations
- Window and maneuver sequence planning for refueling and servicing missions
- Cooperative orbit design for servicer and client spacecraft

> No corresponding implementation in the current version; listed on the roadmap.

### 3. Cislunar Technologies (Planned)

Target direction: supporting deep-space domain awareness and operations, advancing cislunar situational representation, orbit cataloging, navigation, communication, and control. Planned coverage:

- Cislunar situational representation and observability analysis
- Orbit cataloging and object association
- Orbit support design for navigation, communication, and control

> No corresponding implementation in the current version; listed on the roadmap.

### Positioning

Transfer Orbit Design belongs to the same cislunar orbit design domain as STK Cislunar Orbit Design (CODE), NASA's General Mission Analysis Tool (GMAT), and Purdue University's Adaptive Trajectory Design (ATD), sharing the same methodological foundation: CR3BP/BR4BP dynamics, differential correction, natural and pseudo-arclength continuation, and ephemeris multiple-shooting correction. Compared with these mature platforms, this tool emphasizes being lightweight and open source: it organizes orbit generation, transfer search, and ephemeris correction through readable scripts and reproducible pipelines, making it easy to trim, extend, or embed into larger mission design workflows — without aiming for feature parity.

## Documentation and Development

- Development conventions: [`docs/development.md`](docs/development.md)
- Algorithm library documentation: [e2m2e online docs](https://cislunarspace.github.io/e2m2e/)
- Local HTML documentation:

```bash
uv run --extra docs python -m sphinx -b html docs/source docs/build/html
```

## License

This project is licensed under the [Apache License 2.0](LICENSE). You may freely use, modify, and distribute this software, provided you retain the copyright and license notices and comply with the patent grant and trademark terms of the license. See the [`LICENSE`](LICENSE) file in the repository root for details.
