# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Scripts for designing two-impulse transfer orbits from Lunar Distant Retrograde Orbits (DRO) to Resonant Orbits (RO) and GEO, reproducing results from Cui et al. (2025). Works in Chinese (comments, print output, docs).

**This repo is scripts-only.** All core algorithms live in the separate `e2m2e` library (sibling repo at `../e2m2e`). The `scripts/` directory is importable as a package via editable install.

## Setup

```bash
pip install -r requirements.txt           # installs deps + this repo as editable
pip install -e /home/ouyangjiahong/codes/e2m2e  # algorithm library
```

Python >=3.10 (3.13 tested). No linter/formatter in this repo.

## Common Commands

```bash
pytest tests/                        # run all tests
pytest tests/scripts/test_file.py    # single test file
pyright                              # type checking (extraPaths includes ../e2m2e)
```

Scripts are run from repo root: `python scripts/<module>/<script>.py`

For full pipeline commands (generate orbits → grid search → optimize → visualize) and config knobs, see `AGENTS.md`.

## Architecture

```
scripts/
  utils/        # Shared constants (common.py, params.py, geo.py) and file helpers
  dro/          # DRO orbit generation
  ro/           # Resonant orbit families (3:1, 3:2, RRO, ARO)
  halo/         # Halo orbit generation
  transfer/     # Grid search + NLP optimization (DRO→RO and DRO→GEO)
  ephemeris/    # CR3BP → ephemeris correction (multiple shooting, homotopy)
  plot_*.py     # Standalone visualization tools
output/         # Generated data (gitignored, created on demand)
tests/          # pytest tests
```

**Pipeline stages** (must run in order):
1. Generate baseline orbits (DRO, RO) → JSON files in `output/`
2. Grid search over departure points (`grid_search.py`) → search results JSON
3. NLP optimization on feasible results (`optimize.py`) → optimization results JSON
4. Visualization and analysis scripts

**DRO→GEO pipeline**: Same structure using `grid_search_dro_geo.py`, `optimize_dro_geo.py`, `plot_search_results_geo.py` (interactive browsing supported via `--interactive`). Target is GEO sphere around Earth.

**Ephemeris correction**: `correct_dro_to_ephemeris.py` (multiple shooting) and `homotopy_dro_to_ephemeris.py` (homotopy λ-continuation). Requires SPICE kernels (`de440.bsp`, `naif0012.tls`).

**Key e2m2e API surface**: `e2m2e.core.CR3BP_System`, `e2m2e.core.CR3BP_Dynamics`, `e2m2e.core.orbit.Orbit`, `e2m2e.core.OrbitFamily`, `e2m2e.transfer.TransferSearch`, `e2m2e.transfer.DROTRONLPOptimizer`, `e2m2e.transfer.load_orbit_from_json`, `e2m2e.transfer.GeoTransferSearch`

## Critical Constants

- **MU = 1.21506683e-2** — do not use rounded `0.01215`
- Defined in both `scripts/utils/common.py` (CR3BP) and `params.py` (adds BR4BP: `M_SUN`, `OMEGA_SUN`, `RHO`)
- `scripts/utils/geo.py` has GEO-specific constants (`R_GEO`, `V_CIRCULAR_GEO`, etc.)

## Key Patterns

- All scripts use `if __name__ == "__main__"` guard (required for Windows multiprocessing)
- Output timestamps use `fonttools.misc.timeTools.timestampNow` (not `time.time()`)
- Hardcoded JSON file paths in `grid_search.py` and `optimize.py` must be updated before running
- Orbit data format: JSON with `states`, `times`, `period`, `orbit_type` keys

## Test Quirks

- `test_data_loading.py` requires pre-generated RO JSON files in `output/ro/`
- Missing e2m2e causes tests to **pass silently** (ImportError caught), not fail

## Plan Tracking

- `plan/` — dated active task plans
- `docs/plan/` — feature-level design plans
- Check `plan/` for in-progress work before starting new tasks
