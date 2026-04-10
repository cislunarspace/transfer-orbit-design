# Implementation Plan: Code Review Fixes

**Date**: 2026-04-10
**Scope**: Fix all issues from full codebase review (43 files, 59 issues)

## Overview

| Severity | Count | Action |
|----------|-------|--------|
| CRITICAL | 4 | Fix all |
| HIGH | 14 | Fix all |
| MEDIUM | 23 | Fix quick-wins (8), defer major refactors (6) |
| LOW | 18 | Fix when bundled with other edits |

---

## Phase 1: Shared Utilities (3 files)

### Step 1.1: `scripts/utils/common.py` — C1, C2, LOW
- Update docstring (remove "phase1_*.py" reference)
- Remove unused `import argparse`
- Replace `T_MOON = 2 * 3.141592653589793` → `T_MOON = 2.0 * math.pi` (add `import math`)
- In `save_family_to_file`: replace `datetime.datetime.now().strftime(...)` with `timestampNow()`, add comment documenting the intentional difference from generation scripts' epoch format
- Add sync comment next to MU constant

### Step 1.2: `scripts/utils/params.py` — C2
- Add `import math`
- Replace `T_MOON = 2 * 3.141592653589793` → `T_MOON = 2.0 * math.pi`
- Add sync comment re: duplicate constants with common.py

### Step 1.3: `scripts/utils/geo.py` — H14, M12
- `detect_geo_sphere_crossing`: Add clarifying docstring that idx is before the crossing
- `check_collision`: Add `ValueError` for non-positive radii

---

## Phase 2: Runtime Safety (3 files)

### Step 2.1: `scripts/ephemeris/plot_ephemeris_correction.py` — C3
- Move `raise FileNotFoundError(...)` from module level into `main()`

### Step 2.2: `scripts/ephemeris/compare_ephemeris_methods.py` — C4, H11
- Add comment documenting early-exit safety (C4 is false positive but worth noting)
- Add comment explaining `1e-6` tolerance rationale (H11)

### Step 2.3: `scripts/plot_single_orbit.py` — H6
- Add None check for `jacobi_constants` at lines 68 and 113

### Step 2.4: `scripts/plot_interactive_orbit_inspector.py` — H7, H8, M13
- Move `plt.ion()` from module level into `main()`
- Add `else` clause in `compute_global_axis_limits` for unknown plane
- Guard against empty family / empty jacobi_values

---

## Phase 3: Test Fixes (4 files)

### Step 3.1: `tests/scripts/test_plot_scripts_helpers.py` — H4, H9
- Replace `except Exception: pass` with `except Exception as e: pytest.skip(...)`
- Add `else` branch to `test_plot_range_from_start` and `test_plot_range_to_end`

### Step 3.2: `tests/scripts/test_generate_family_helpers.py` — H4
- Replace `except ImportError: pass` with `pytest.skip` / `pytest.fail`

### Step 3.3: `tests/scripts/test_ephemeris_correction.py` — H4
- Replace `except ImportError: pass` with `pytest.skip`

### Step 3.4: `tests/scripts/test_data_loading.py` — H10
- Add `pytest.skip` guards for `test_output_directory_exists` and `test_there_are_json_files`

---

## Phase 4: Generator Scripts (9 files)

### Step 4.1: Add `if __name__ == "__main__"` guards — H2
Wrap top-level execution in `def main():` with guard for:
1. `scripts/dro/generate_dro_family.py`
2. `scripts/dro/generate_31_dro_orbit.py`
3. `scripts/ro/generate_31_ro_family.py`
4. `scripts/ro/generate_31_ro_orbit.py`
5. `scripts/ro/generate_32_ro_family.py`
6. `scripts/ro/generate_rro_family.py` — also fix `dir()` → `locals()`
7. `scripts/ro/generate_aro_family.py` — also fix `dir()` → `locals()`
8. `scripts/halo/generate_halo_orbit.py` — also remove duplicate `project_root`, fix `z0 = amplitude_z`
9. `scripts/halo/generate_halo_family.py`

### Step 4.2: Fix double `timestampNow()` calls — H1
Store `ts = timestampNow()` once per script, reuse in filename and print.

---

## Phase 5: Plot Scripts (6 files)

### Step 5.1: Add error handling for hardcoded paths — H3
Add file-existence check with helpful error message for:
- `scripts/dro/plot_dro_family.py`
- `scripts/ro/plot_31_ro_family.py`, `plot_32_ro_family.py`, `plot_rro_family.py`, `plot_aro_family.py`
- `scripts/halo/plot_halo_orbit.py`

### Step 5.2: Replace magic number `4.348` with `TU` — M8
Files: `plot_single_orbit.py`, `plot_interactive_orbit_inspector.py`, `plot_31/32/rro/aro_ro_family.py`

---

## Phase 6: Transfer Scripts (2 files)

### Step 6.1: `scripts/transfer/optimize_dro_geo.py` — H5, LOW
- Replace `1023.23` with imported `VU`
- Remove unused `import threading`

### Step 6.2: `scripts/transfer/plot_search_results_geo.py` — H12
- Filter out `None` results in multi-orbit plotting with warning

---

## Deferred (Not Fixing)

| Issue | Reason |
|-------|--------|
| M4: Functions >50 lines | Scientific scripts, readability > splitting |
| M5: Files >800 lines | Major refactoring, low ROI for scripts |
| M9: O(N*M) memory | Requires optimization loop redesign |
| M10: Velocity model inconsistency | Needs physics review |
| M2: Duplicated `_json_safe` | 5-line function, cross-module dep not worth it |
| M3: Duplicated departure velocity | Same reasoning |

---

## Verification

```bash
pytest tests/ -v    # expect 69 pass, 2 skip
pyright             # expect no new errors
```

## Success Criteria

- [ ] All 4 CRITICAL fixed
- [ ] All 14 HIGH fixed
- [ ] 8 MEDIUM quick-wins fixed
- [ ] Tests pass (69 pass, 2 skip)
- [ ] No hardcoded `3.141592653589793`
- [ ] No import-time side effects
- [ ] No silent `except Exception: pass` in tests
- [ ] All scripts have `__main__` guards
