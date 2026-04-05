# OpenCode Agent Guidance

## Project Overview
- **Purpose**: Reproduce "Two-Impulse Transfers from Lunar Distant Retrograde Orbits to Resonant Orbits" (Cui et al., 2025)
- **Core task**: Design transfer orbits between DRO (Distant Retrograde Orbits) and RO (Resonant Orbits) in Earth-Moon system
- **Methodology**: Two-phase approach: grid search → NLP optimization

## Critical Setup Requirements
- **Local dependency**: Must install `e2m2e` library locally: `pip install -e /path/to/e2m2e`
- **Editable install**: Run `pip install -e .` after cloning to make `scripts/` imports work from any directory
- **Python version**: 3.13 recommended (via conda environment `orbit-py313`)

## Key Commands & Workflow
### 1. Generate Baseline Orbits
```bash
python scripts/dro/generate_31_dro_orbit.py          # Single 3:1 DRO
python scripts/dro/generate_dro_family.py            # DRO family
python scripts/ro/generate_31_ro_family.py           # 3:1 RO family
python scripts/ro/generate_32_ro_family.py           # 3:2 RO family
```

### 2. Transfer Design Pipeline
```bash
# 1. Grid search (requires DRO/RO JSON files in output/)
python scripts/transfer/grid_search.py

# 2. NLP optimization of search results
python scripts/transfer/optimize.py

# 3. Visualize results
python scripts/transfer/plot_search_results.py <results.json>
```

### 3. Visualization
```bash
python scripts/plot_single_orbit.py <orbit.json>     # Single orbit 2D/3D
python scripts/plot_interactive_orbit_inspector.py   # Interactive inspection
```

## Architecture Notes
- **Core algorithms**: In `e2m2e` library (separate repository)
- **This repo**: Contains task scripts in `scripts/` that use `e2m2e` APIs
- **Output structure**: `output/dro/`, `output/ro/`, `output/transfer/`
- **Data format**: JSON files with `states`, `times`, `period`, `orbit_type` keys

## Important Conventions
- **Units**: DU (384405 km), TU (4.34811305 days), VU (1023.23281 m/s)
- **Mass ratio**: μ = 1.21506683e-2 (Earth-Moon system)
- **File naming**: Timestamp suffixes ensure unique output files
- **Windows multiprocessing**: Scripts use `if __name__ == "__main__"` protection

## Testing & Verification
- **Test directory**: `tests/` contains unit tests
- **No CI/CD**: No GitHub Actions workflows found
- **Type checking**: Configured via `pyproject.toml` with `tool.pyright`

## Common Pitfalls
1. **Missing e2m2e**: Scripts will fail with `ModuleNotFoundError: No module named 'e2m2e'`
2. **Wrong working directory**: Run scripts from repo root after `pip install -e .`
3. **Missing orbit data**: Grid search requires pre-generated DRO/RO JSON files
4. **Large computations**: Grid search uses multiprocessing; monitor memory usage

## Development Notes
- **Style**: Follow existing patterns in `scripts/utils/common.py` for constants
- **Documentation**: See `docs/` for theory and algorithm explanations
- **Plan tracking**: Progress tracked in `plan/` directory markdown files