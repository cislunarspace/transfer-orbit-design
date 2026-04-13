# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Scripts for designing two-impulse transfer orbits between Lunar Distant Retrograde Orbits (DRO), Resonant Orbits (RO), GEO, and LEO, reproducing results from Cui et al. (2025). Works in Chinese (comments, print output, docs).

**This repo is scripts-only.** All core algorithms live in the separate `e2m2e` library (sibling repo at `../e2m2e`). The `scripts/` directory is importable as a package via editable install.

## Setup

```bash
conda create -n orbit-py313 python=3.13 && conda activate orbit-py313
pip install -r requirements.txt           # installs deps + this repo as editable (-e .)
pip install -e /home/ouyangjiahong/codes/e2m2e  # algorithm library (sibling repo)
```

- `requirements.txt` ends with `-e .` — no separate editable install needed for this repo
- e2m2e can also be installed from gitee: `pip install "e2m2e @ git+https://gitee.com/cislunarspace/e2m2e.git"`
- e2m2e has its own `AGENTS.md` — consult it before modifying e2m2e code
- Dev deps: `pip install -e ".[dev]"` or just `pip install pytest`
- Python >=3.10 (3.13 tested). No linter/formatter in this repo (Ruff lives in e2m2e).

## Common Commands

```bash
pytest tests/                        # run all tests
pytest tests/scripts/test_file.py    # single test file
pyright                              # type checking (extraPaths includes ../e2m2e)
```

Scripts are run from repo root: `python scripts/<module>/<script>.py`

```bash
python scripts/gui/main.py             # launch PyQt6 GUI
```

## Transfer Pipelines (order matters within each)

### DRO → RO
```bash
python scripts/transfer/grid_search_dro_to_ro.py   # 1. grid search
python scripts/transfer/optimize_dro_to_ro.py      # 2. NLP optimization
python scripts/transfer/plot_search_results.py <results.json> [--time-dv] [--orbit] [--idx N]
```

### DRO → GEO
```bash
python scripts/transfer/grid_search_dro_to_geo.py
python scripts/transfer/optimize_dro_to_geo.py
python scripts/transfer/plot_search_results_geo.py <results.json>
python scripts/transfer/plot_optimize_result.py <results.json>
```

### GEO → DRO
```bash
python scripts/transfer/grid_search_geo_to_dro.py
python scripts/transfer/optimize_geo_to_dro.py
python scripts/transfer/plot_search_results_geo_to_dro.py <results.json>
python scripts/transfer/plot_optimize_result_geo_to_dro.py <results.json>
```

### LEO → DRO
```bash
python scripts/transfer/grid_search_leo_to_dro.py
python scripts/transfer/optimize_leo_to_dro.py
```

### Ephemeris Correction (CR3BP → ephemeris)
```bash
python scripts/ephemeris/correct_dro_to_ephemeris.py    # multiple shooting
python scripts/ephemeris/homotopy_dro_to_ephemeris.py   # homotopy λ-continuation
```
Requires SPICE kernels (`de440.bsp`, `naif0012.tls`) in `e2m2e/kernels/`. Set `SPICE_KERNEL_DIR` env var or use default `../e2m2e/kernels`.

### Generate Baseline Orbits
```bash
python scripts/dro/generate_31_dro_orbit.py     # single 3:1 DRO
python scripts/dro/generate_dro_family.py        # DRO family
python scripts/ro/generate_31_ro_orbit.py        # single 3:1 RO
python scripts/ro/generate_31_ro_family.py       # 3:1 RO family
python scripts/ro/generate_32_ro_family.py       # 3:2 RO family
python scripts/ro/generate_rro_family.py         # 3D RRO family
python scripts/ro/generate_aro_family.py         # 3D ARO family
python scripts/halo/generate_halo_orbit.py       # single Halo orbit
python scripts/halo/generate_halo_family.py      # Halo orbit family
```

## Architecture

**This repo is scripts-only.** All core algorithms live in the separate `e2m2e` library (sibling repo at `../e2m2e`). The `scripts/` directory is importable as a package via editable install so `from scripts.utils.common import ...` works from any working directory.

```
scripts/
  utils/           # Shared constants (constants.py) and file helpers (common.py, geo.py, leo.py)
  dro/             # DRO orbit generation
  ro/              # Resonant orbit families (3:1, 3:2, RRO, ARO)
  halo/            # Halo orbit generation
  transfer/        # Grid search + NLP optimization (DRO↔RO, DRO↔GEO, GEO↔DRO, LEO↔DRO)
  ephemeris/       # CR3BP → ephemeris correction (multiple shooting, homotopy)
  inspection/      # Standalone orbit visualization tools
  gui/             # PyQt6 GUI — browse & run scripts with parameter controls
output/            # Generated data (gitignored, created on demand)
tests/             # pytest tests
```

**Pipeline stages** (must run in order):
1. Generate baseline orbits (DRO, RO) → JSON files in `output/`
2. Grid search over departure points → search results JSON
3. NLP optimization on feasible results → optimization results JSON
4. Visualization and analysis scripts

**Key e2m2e API surface**: `e2m2e.core.CR3BP_System`, `e2m2e.core.CR3BP_Dynamics`, `e2m2e.core.orbit.Orbit`, `e2m2e.core.OrbitFamily`, `e2m2e.transfer.TransferSearch`, `e2m2e.transfer.DROTRONLPOptimizer`, `e2m2e.transfer.GeoTransferSearch`, `e2m2e.transfer.load_orbit_from_json`

## Constants

| File | Exports |
|------|---------|
| `scripts/utils/constants.py` | All physical constants: `MU, DU, TU, VU, T_MOON, M_SUN, OMEGA_SUN, RHO` |
| `scripts/utils/common.py` | Re-exports constants + file helpers (`ensure_output_dir`, `get_latest_family_file`, `save_family_to_file`) |
| `scripts/utils/geo.py` | GEO orbit constants (`R_GEO`, `EARTH_CENTER`, `V_CIRCULAR_GEO`, `T_GEO`) + helpers |
| `scripts/utils/leo.py` | LEO orbit constants (`R_LEO`, `V_CIRCULAR_LEO`, `T_LEO`) at 400 km altitude |

**μ = 1.21506683e-2** — do not use the rounded `0.01215`.

`FAMILY_FILENAME = "family.json"` — standard filename for orbit family JSON files.

## GUI

PyQt6 desktop app (`scripts/gui/main.py`) for browsing and running scripts.
- `script_registry.py` — `ScriptEntry` dataclass metadata for every script (module, description, env params, CLI params)
- `main_window.py` — tabbed UI grouped by module (DRO, RO, Halo, Transfer, Ephemeris, Inspection)
- `job_manager.py` — multi-process manager, one QProcess per job with job_id routing
- `output_panel.py` — per-job structured output (ANSI stripping, timestamps, stderr coloring) + JobCard widget
- `file_discovery.py` — finds JSON files in `output/` for file-selection dropdowns
- `CliParam` with non-None `file_category` also renders as file dropdown (editable combo)
- Scripts with `env_params` get file picker dropdowns; other `cli_params` get typed input controls

## Key Patterns

- All scripts use `if __name__ == "__main__"` guard (required for Windows multiprocessing)
- Output timestamps use `int(time.time())`
- Orbit data format: JSON with `states` (Nx6 arrays), `times`, `period`, `orbit_type` keys
- Transfer script naming: `{action}_{source}_to_{target}.py`
- All scripts use `argparse` for CLI parameters

## File Naming Conventions

- Single orbit: `dro_31_<timestamp>.json`
- Family: `ro_31_family_<x0_range>_<timestamp>.json`
- Family "latest" copy: `family.json` (overwritten each run — do not rely on it)
- Search results: `search_results_{nDep}-{nAlpha}-{amin}-{amax}-{tmax}_{timestamp}.json`
- Optimization: `optimization_results_<timestamp>.json` / `optimization_dro_geo_<timestamp>.json`

## Hardcoded Paths — Must Edit Before Running

- `scripts/transfer/grid_search_dro_to_ro.py`: DRO/RO file paths hardcoded near `main()`
- `scripts/transfer/optimize_dro_to_ro.py`: `SEARCH_RESULTS_FILE`, `DRO_FILE`, `RO_FILE` constants (~lines 48-52)
- `scripts/transfer/grid_search_dro_to_geo.py`: DRO file path hardcoded
- `scripts/transfer/optimize_dro_to_geo.py`: search results file path hardcoded
- Recent work has added CLI/env var overrides for some of these — check `parse_args()` first

## optimize_* Config Knobs

- `USE_COPT=False` — enable with `pip install coptpy`; `FALLBACK_TO_SCIPY=True` auto-falls back
- `USE_RELAXED_VELOCITY=True` / `VELOCITY_ANGLE_TOL=0.05` — velocity direction tolerance
- `COMPUTE_T_INS_FROM_TRAJECTORY=True` — derive insertion time from trajectory
- `N_WORKERS`, `PARALLEL_BACKEND="processes"`, `TOP_K_FEASIBLE`, `MAX_CASES`
- Env vars: `OPTIMIZE_NO_TQDM=1`, `OPTIMIZE_BLAS_THREADS_PER_WORKER`

## Test Quirks

- `test_data_loading.py` requires pre-generated RO JSON files in `output/ro/` — generate RO family first or skip
- Missing e2m2e causes tests to **pass silently** (ImportError caught via `pytest.skip`), not fail
- Tests use `matplotlib.use("Agg")` for headless plotting
- Tests are lightweight: mostly parameter validation and import checking, not numerical correctness

## Common Pitfalls

1. **Missing e2m2e**: `ModuleNotFoundError: No module named 'e2m2e'` — run `pip install -e <path/to/e2m2e>`
2. **Wrong working directory**: Always run scripts from repo root after editable install
3. **Stale hardcoded paths**: `grid_search_dro_to_ro.py` and `optimize_dro_to_ro.py` have hardcoded JSON file paths — update them before running
4. **μ precision**: Always use `MU = 1.21506683e-2`, never the rounded `0.01215`

## Cross-Platform Notes

This project supports **Windows, Linux, and macOS**.

### Line Endings
- `.gitattributes` enforces LF for all text files (`.py`, `.md`, `.json`, `.yml`, `.toml`)
- Windows batch/PowerShell scripts use CRLF
- After cloning, run `git config core.autocrlf input` (or `false`) on Windows

### Python Executable
- GUI uses `sys.executable` to launch child processes (works on all platforms)
- On Linux/macOS, if `python` is not found, use `python3` directly in terminal
- Scripts use `if __name__ == "__main__"` guard for Windows multiprocessing compatibility

### PyQt6 System Dependencies
- **Linux**: May need `sudo apt install libxcb-xinerama0 libxcb-cursor0` (or equivalent)
- **macOS**: `pip install PyQt6` should work out of the box
- **Windows**: Wheels include all dependencies

### SPICE Kernels
- Default path: `../e2m2e/kernels/` (sibling directory, works on all OS via `pathlib`)
- Override with `SPICE_KERNEL_DIR` environment variable for non-standard layouts

### CI/CD
- GitHub Actions runs tests on all three platforms (Windows, Linux, macOS) with Python 3.10 and 3.13
- Release workflow triggers on `v*` tags to create GitHub Releases

## Plan Tracking

- `plan/` — dated active task plans
- Check `plan/` for in-progress work before starting new tasks
