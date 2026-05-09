# OpenCode Agent Guidance

## Setup
```bash
conda create -n orbit-py313 python=3.13 && conda activate orbit-py313
uv sync                                # installs deps + e2m2e from local sibling + this repo as editable
```
- `pyproject.toml` ends with `e2m2e @ file:///C:/Users/ouyan/codes/e2m2e` — no separate editable install needed for e2m2e
- e2m2e has its own `AGENTS.md` — consult it before modifying e2m2e code
- Dev deps: `pytest` is included; linter/formatter lives in e2m2e, not here
- Python `>=3.11`; `3.13` tested

## Key Commands

### Generate Baseline Orbits
```bash
python -m tod.pipelines.dro.generate.generate_31_dro_orbit     # single 3:1 DRO
python -m tod.pipelines.dro.generate.generate_dro_family        # DRO family
python -m tod.pipelines.ro.generate.generate_31_ro_orbit         # single 3:1 RO
python -m tod.pipelines.ro.generate.generate_31_ro_family        # 3:1 RO family
python -m tod.pipelines.ro.generate.generate_32_ro_family       # 3:2 RO family
python -m tod.pipelines.ro.generate.generate_rro_family          # 3D RRO family
python -m tod.pipelines.ro.generate.generate_aro_family           # 3D ARO family
python -m tod.pipelines.halo.generate.generate_halo_orbit       # single Halo orbit
python -m tod.pipelines.halo.generate.generate_halo_family      # Halo orbit family
```

### DRO → RO Transfer Pipeline (order matters)
```bash
python -m tod.pipelines.transfer.dro_to_ro.grid_search   # 1. Grid search
python -m tod.pipelines.transfer.dro_to_ro.optimize      # 2. NLP optimization
```

### DRO → GEO Transfer Pipeline
```bash
python -m tod.pipelines.transfer.dro_to_geo.grid_search   # grid search to GEO sphere
python -m tod.pipelines.transfer.dro_to_geo.optimize      # NLP optimization
```

### GEO → DRO Transfer Pipeline
```bash
python -m tod.pipelines.transfer.geo_to_dro.grid_search
python -m tod.pipelines.transfer.geo_to_dro.optimize
```

### LEO → DRO Transfer Pipeline
```bash
python -m tod.pipelines.transfer.leo_to_dro.grid_search
python -m tod.pipelines.transfer.leo_to_dro.optimize
```

### Ephemeris Correction (CR3BP → ephemeris)
```bash
python -m tod.pipelines.ephemeris.correct.correct_dro_to_ephemeris    # Multiple Shooting method
python -m tod.pipelines.ephemeris.correct.homotopy_dro_to_ephemeris   # homotopy λ-continuation method
python -m tod.pipelines.ephemeris.compare.compare_ephemeris_methods   # benchmark both methods
```
- Requires SPICE kernels (`de440.bsp`, `naif0012.tls`) in `e2m2e/kernels/`
- Kernel path: set `SPICE_KERNEL_DIR` env var; default is `../e2m2e/kernels` (works when repos are siblings)

### Tests & Type Checking
```bash
pytest tests/                           # all tests
pytest tests/tod/test_params.py           # single file
pyright                                 # configured in pyproject.toml; extraPaths = ["../e2m2e"]
```

## Architecture
- **This repo**: Scripts only — not a library. `tod/` is importable as a package so `from tod.commons import ...` works after editable install
- **All algorithms**: In `e2m2e` (separate repo). Key public API: `e2m2e.core`, `e2m2e.algorithms`, `e2m2e.transfer`, `e2m2e.visualization`, `e2m2e.orbits`
- **Output directories**: `tod/pipelines/output/dro/`, `tod/pipelines/output/ro/`, etc. (created on demand)
- **Data format**: JSON with `states`, `times`, `period`, `orbit_type` keys
- **Transfer naming**: `{action}_{source}_to_{target}.py` convention

## Constants — Source of Truth
| File | Exports |
|------|---------|
| `tod/commons/constants.py` | CR3BP constants from `e2m2e.CR3BP_System`: `MU, DU, TU, VU, T_MOON`; BR4BP: `M_SUN, OMEGA_SUN, RHO`; `FAMILY_FILENAME` |
| `tod/commons/io.py` | File helpers (`ensure_output_dir`, `get_latest_family_file`, `save_family_to_file`, `load_or_compute`) |
| `e2m2e.orbits.geo` | GEO orbit constants (`R_GEO`, `EARTH_CENTER`, `V_CIRCULAR_GEO`, `T_GEO`) + sphere crossing, dv2, collision helpers |
| `e2m2e.orbits.leo` | LEO orbit constants + helpers |

- **μ = 1.21506683e-2** — from `e2m2e.CR3BP_System.from_known_system("earth_moon")`. Do not use the rounded `0.01215`

## Hardcoded Paths — Must Edit Before Running
- `tod/pipelines/transfer/dro_to_ro/grid_search.py`: DRO/RO file paths hardcoded near `main()` — update to match your generated files
- `tod/pipelines/transfer/dro_to_ro/optimize.py`: hardcoded file paths at top
- `tod/pipelines/transfer/dro_to_geo/grid_search.py`: DRO file path hardcoded
- `tod/pipelines/transfer/dro_to_geo/optimize.py`: search results file path hardcoded

## optimize_* Config Knobs
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
- Search results: `search_results_{nDep}-{nAlpha}-{αmin}-{αmax}-{tmax}_{timestamp}.json`
- Optimization: `optimization_results_<timestamp>.json` / `optimization_dro_geo_<timestamp>.json`

## Test Quirks
- `tests/tod/test_data_loading.py` requires `tod/pipelines/output/ro/*.json` to exist — skip or generate RO family first
- Missing e2m2e causes import tests to **pass silently** (ImportError is caught), not fail
- All scripts use `if __name__ == "__main__"` guard — required on Windows for multiprocessing

## Common Pitfalls
1. **Missing e2m2e**: `ModuleNotFoundError: No module named 'e2m2e'` — run `uv sync`
2. **Wrong working directory**: Always run scripts from repo root after editable install
3. **Stale hardcoded paths**: `grid_search_dro_to_ro.py` and `optimize_dro_to_ro.py` have hardcoded JSON file paths — update them

## Plan Tracking
- `plan/` — dated active task plans (e.g. `2026-04-06-dro-to-geo-transfer.md`)
- `docs/plan/` — feature-level design plans
- Check `plan/` for in-progress work before starting new tasks
