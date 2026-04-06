# OpenCode Agent Guidance

## Setup
```bash
conda create -n orbit-py313 python=3.13 && conda activate orbit-py313
pip install -r requirements.txt           # installs deps + this repo as editable (-e .)
pip install -e /home/ouyangjiahong/codes/e2m2e  # sibling repo, v3.1.11
```
- `requirements.txt` ends with `-e .` — no separate editable install needed for this repo
- e2m2e can also be installed from gitee: `pip install "e2m2e @ git+https://gitee.com/cislunarspace/e2m2e.git"` (see `environment.yml`)
- e2m2e has its own `AGENTS.md` — consult it before modifying e2m2e code
- Dev deps: `pip install -e ".[dev]"` or just `pip install pytest`
- Python `>=3.10`; `3.13` tested

## Key Commands

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

### DRO → RO Transfer Pipeline (order matters)
```bash
# 1. Grid search — requires pre-generated DRO/RO JSON files
python scripts/transfer/grid_search.py

# 2. NLP optimization
python scripts/transfer/optimize.py

# 3. Visualize
python scripts/transfer/plot_search_results.py <results.json> [--time-dv] [--orbit] [--idx N] [--save]
python scripts/transfer/plot_optimize_result.py <optimization_results.json>
```

### DRO → GEO Transfer Pipeline
```bash
python scripts/transfer/grid_search_dro_geo.py   # grid search to GEO sphere
python scripts/transfer/optimize_dro_geo.py      # NLP optimization
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

### Tests & Type Checking
```bash
pytest tests/                        # all tests
pytest tests/scripts/<test_file.py>  # single file
pyright                              # configured in pyproject.toml; extraPaths = ["../e2m2e"]
```
- No linter or formatter in this repo (Ruff lives in e2m2e, not here)

## Architecture
- **This repo**: Scripts only — not a library. `scripts/` is importable as a package so `from scripts.utils.common import ...` works after editable install
- **All algorithms**: In `e2m2e` (separate repo). Key public API: `e2m2e.core`, `e2m2e.algorithms`, `e2m2e.transfer`, `e2m2e.visualization`
- **Output directories**: `output/dro/`, `output/ro/`, `output/transfer/`, `output/ephemeris/` (created on demand)
- **Data format**: JSON with `states`, `times`, `period`, `orbit_type` keys

## Constants — Three Files
| File | Exports |
|------|---------|
| `scripts/utils/common.py` | `MU, DU, TU, VU, T_MOON` + file helpers (`ensure_output_dir`, `get_latest_family_file`, `load_or_compute`, `save_family_to_file`) |
| `scripts/utils/params.py` | Duplicates `common.py` constants plus BR4BP params: `M_SUN`, `OMEGA_SUN`, `RHO` |
| `scripts/utils/geo.py` | GEO orbit constants (`R_GEO`, `EARTH_CENTER`, `V_CIRCULAR_GEO`, `T_GEO`) + helpers for GEO sphere crossing, dv2, collision detection |

- **μ = 1.21506683e-2** — do not use the rounded `0.01215`

## Non-Obvious Dependency
- **`fonttools.misc.timeTools.timestampNow`** — used for all output file timestamps. It's in `requirements.txt` but the import path is surprising; not `time.time()`.

## Hardcoded Paths — Must Edit Before Running
- `scripts/transfer/grid_search.py`: DRO/RO file paths hardcoded near `main()` — update to match your generated files
- `scripts/transfer/optimize.py`: `SEARCH_RESULTS_FILE`, `DRO_FILE`, `RO_FILE` constants at top of file (~lines 48-52)
- `scripts/transfer/grid_search_dro_geo.py`: DRO file path hardcoded
- `scripts/transfer/optimize_dro_geo.py`: search results file path hardcoded

## optimize.py Config Knobs
- `USE_COPT=False` — enable with `pip install coptpy`; `FALLBACK_TO_SCIPY=True` auto-falls back
- `USE_RELAXED_VELOCITY=True` — velocity direction tolerance for feasibility
- `VELOCITY_ANGLE_TOL=0.05` — angle tolerance (rad) when relaxed velocity is on
- `COMPUTE_T_INS_FROM_TRAJECTORY=True` — derive insertion time from trajectory rather than grid
- `OPTIMIZE_NO_TQDM=1` env var disables progress bar
- `OPTIMIZE_BLAS_THREADS_PER_WORKER` env var overrides per-worker BLAS thread limit (default 1)
- `N_WORKERS`, `PARALLEL_BACKEND="processes"`, `TOP_K_FEASIBLE`, `MAX_CASES` — all configurable at top of file

## File Naming Conventions
- Single orbit: `dro_31_<timestamp>.json`
- Family: `ro_31_family_<x0_range>_<timestamp>.json`
- Family "latest" copy: `family.json` (overwritten each run — do not rely on it)
- Search results: `search_results_{nDep}-{nAlpha}-{αmin}-{αmax}-{tmax}_{timestamp>.json`
- Optimization: `optimization_results_<timestamp>.json` / `optimization_dro_geo_<timestamp>.json`

## Test Quirks
- `tests/scripts/test_data_loading.py` requires `output/ro/*.json` to exist — skip or generate RO family first
- Missing e2m2e causes import tests to **pass silently** (ImportError is caught), not fail
- All scripts use `if __name__ == "__main__"` guard — required on Windows for multiprocessing

## Common Pitfalls
1. **Missing e2m2e**: `ModuleNotFoundError: No module named 'e2m2e'` — run `pip install -e <path/to/e2m2e>`
2. **Wrong working directory**: Always run scripts from repo root after editable install
3. **Stale hardcoded paths**: `grid_search.py` and `optimize.py` have hardcoded JSON file paths — update them

## Plan Tracking
- `plan/` — dated active task plans (e.g. `2026-04-06-dro-to-geo-transfer.md`)
- `docs/plan/` — feature-level design plans
- Check `plan/` for in-progress work before starting new tasks
