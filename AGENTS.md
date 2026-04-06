# OpenCode Agent Guidance

## Project Overview
- **Purpose**: Reproduce "Two-Impulse Transfers from Lunar Distant Retrograde Orbits to Resonant Orbits" (Cui et al., 2025)
- **Core task**: Design transfer orbits between DRO and RO in Earth-Moon system
- **Methodology**: Two-phase approach: grid search → NLP optimization

## Setup
```bash
# Full setup from scratch
conda create -n orbit-py313 python=3.13 && conda activate orbit-py313
pip install -r requirements.txt           # installs deps + this repo as editable (-e .)
pip install -e C:\Users\ouyan\codes\e2m2e # install sibling e2m2e repo separately
```
- `e2m2e` lives at `C:\Users\ouyan\codes\e2m2e` (sibling directory, version 3.1.11)
- `e2m2e` has its own `AGENTS.md` — consult it before modifying e2m2e code
- `pip install -r requirements.txt` already includes `-e .` at the end — no separate editable install needed
- Dev extras (pytest, etc.): `pip install -e ".[dev]"` or `pip install pytest`
- Python `>=3.10` required; `3.13` tested

## Key Commands

### Generate Baseline Orbits
```bash
python scripts/dro/generate_31_dro_orbit.py     # single 3:1 DRO
python scripts/dro/generate_dro_family.py        # DRO family
python scripts/ro/generate_31_ro_family.py       # 3:1 RO family
python scripts/ro/generate_32_ro_family.py       # 3:2 RO family
```

### Transfer Design Pipeline (order matters)
```bash
# 1. Grid search — requires pre-generated DRO/RO JSON files
python scripts/transfer/grid_search.py

# 2. NLP optimization
python scripts/transfer/optimize.py

# 3. Visualize
python scripts/transfer/plot_search_results.py <results.json> [--time-dv] [--orbit] [--idx N] [--save]
python scripts/transfer/plot_optimize_result.py <optimization_results.json>
```

### Ephemeris Correction (CR3BP → ephemeris)
```bash
python scripts/ephemeris/correct_dro_to_ephemeris.py    # Multiple Shooting method
python scripts/ephemeris/homotopy_dro_to_ephemeris.py   # homotopy λ-continuation method
python scripts/ephemeris/compare_ephemeris_methods.py   # benchmark both methods
python scripts/ephemeris/plot_ephemeris_correction.py   # visualize results
```
- Requires SPICE kernels (`de440.bsp`, `naif0012.tls`) in `e2m2e/kernels/`
- Kernel path: set `SPICE_KERNEL_DIR` env var; default is `../e2m2e/kernels` (works when repos are siblings)

### Visualization
```bash
python scripts/plot_single_orbit.py <orbit.json>
python scripts/plot_interactive_orbit_inspector.py
```

### Tests
```bash
pytest tests/                        # all tests
pytest tests/scripts/<test_file.py>  # single file
```
- `tests/scripts/test_data_loading.py` requires `output/ro/*.json` to exist — skip or generate RO family first
- Missing `e2m2e` causes import tests to **pass silently** (ImportError is caught), not fail

### Type Checking
```bash
pyright   # configured in pyproject.toml; extraPaths = ["../e2m2e"]
```
- No linter or formatter configured in this repo (Ruff lives in `e2m2e`, not here)

## Architecture
- **This repo**: Scripts only — not a library. `scripts/` is importable as a package so `from scripts.utils.common import ...` works after editable install
- **All algorithms**: In `e2m2e` (separate repo). Key public API: `e2m2e.core`, `e2m2e.algorithms`, `e2m2e.transfer`, `e2m2e.visualization`
- **Output directories**: `output/dro/`, `output/ro/`, `output/halo/`, `output/transfer/`, `output/ephemeris/`
- **Data format**: JSON with `states`, `times`, `period`, `orbit_type` keys

## Constants — Two Files
| File | Exports |
|------|---------|
| `scripts/utils/common.py` | `MU, DU, TU, VU, T_MOON` + file helpers (`ensure_output_dir`, `get_latest_family_file`, `load_or_compute`, `save_family_to_file`) |
| `scripts/utils/params.py` | All of `common.py` plus BR4BP params: `M_SUN=3.28900541e5`, `OMEGA_SUN=9.25195985e-1`, `RHO=3.88811143e2` |

Use `params.py` when BR4BP parameters are needed; use `common.py` otherwise.

## Units & Physical Constants
- **DU** = 384405 km, **TU** = 4.34811305 days, **VU** = 1023.23281 m/s
- **μ** = 1.21506683e-2 (canonical; do not use the rounded `0.01215`)

## File Naming Conventions
- Single orbit: `dro_31_<timestamp>.json`
- Family: `ro_31_family_<x0_range>_<timestamp>.json`
- Family "latest" symlink copy: `family.json` (overwritten each run — do not rely on it)
- Search results: `search_results_{nDep}-{nAlpha}-{αmin}-{αmax}-{tmax}_{timestamp}.json`
- Timestamps via `fonttools.misc.timeTools.timestampNow` (non-obvious dep)

## Hardcoded Paths — Must Edit Before Running
- `scripts/transfer/grid_search.py`: DRO/RO file paths are hardcoded at specific timestamps near `main()` — update to match your generated files
- `scripts/transfer/optimize.py`: `SEARCH_RESULTS_FILE`, `DRO_FILE`, `RO_FILE` constants at top of file

## optimize.py Config Knobs
- `USE_COPT=False` — enable with `pip install coptpy`
- `USE_RELAXED_VELOCITY=False` — enable if NLP doesn't converge
- `OPTIMIZE_NO_TQDM=1` env var disables progress bar
- `OPTIMIZE_BLAS_THREADS_PER_WORKER` env var overrides per-worker BLAS thread limit

## Common Pitfalls
1. **Missing e2m2e**: `ModuleNotFoundError: No module named 'e2m2e'` — run `pip install -e <path/to/e2m2e>`
2. **Wrong working directory**: Always run scripts from repo root after editable install
3. **Stale hardcoded paths**: `grid_search.py` and `optimize.py` have hardcoded JSON file paths — update them
4. **test_data_loading.py fails**: Requires `output/ro/` with `.json` files to exist
5. **Windows multiprocessing**: All scripts use `if __name__ == "__main__"` guard — required on Windows

## Plan Tracking
- `plan/` — dated active task plans (e.g. `2026-04-05-compare-ephemeris-methods.md`)
- `docs/plan/` — feature-level design plans
- Check `plan/` for in-progress work before starting new tasks
