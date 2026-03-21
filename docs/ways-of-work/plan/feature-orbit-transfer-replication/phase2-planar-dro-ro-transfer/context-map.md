## Context Map

### Files Modified

| File | Purpose | Changes Made |
|------|---------|--------------|
| `e2m2e/e2m2e/transfer/dro_ro_search.py` | **NEW** - Search phase implementation | Created with `TransferSearchVariables`, `TransferSearchResult`, `DROROTransferSearch` |
| `e2m2e/e2m2e/transfer/__init__.py` | Module exports | Added exports for new classes |
| `e2m2e/tests/transfer/test_dro_ro_search.py` | **NEW** - Tests for search phase | Created 15 tests for TASK-009 |
| `e2m2e/tests/transfer/__init__.py` | **NEW** - Test package init | Created |

### Dependencies (may need updates)

| File | Relationship |
|------|--------------|
| `e2m2e/e2m2e/core/orbit.py` | `Orbit` class - provides `interpolate_at_time()` for sampling |
| `e2m2e/e2m2e/core/dynamics.py` | `CR3BP_Dynamics` class - provides `propagate()` for forward integration |
| `e2m2e/e2m2e/core/system.py` | `CR3BP_System` class - provides `mu` and system parameters |

### Test Files

| Test | Coverage |
|------|----------|
| `e2m2e/tests/core/orbit/test_orbit.py` | Existing Orbit tests - reference for test patterns |
| `e2m2e/tests/core/dynamics/test_dynamics.py` | Existing Dynamics tests - reference for integration testing |
| `tests/transfer/test_inter_orbit_search.py` (new) | Tests for search algorithm |

### Reference Patterns

| File | Pattern |
|------|---------|
| `e2m2e/e2m2e/transfer/inter_orbit.py` | `InterOrbitTransfer` class structure - follow same architecture |
| `e2m2e/e2m2e/core/orbit.py` | `Orbit` class with `interpolate_at_time()` method |
| `transfer-orbit-design/output/dro/dro_family_*.json` | DRO family data format for loading test data |

### Risk Assessment
- [ ] Breaking changes to public API - No, adding new class
- [ ] Database migrations needed - No
- [ ] Configuration changes required - No

---

## Implementation Strategy

### TASK-009 Sub-tasks

1. **SUB-009-01**: Create `TransferSearchVariables` dataclass
2. **SUB-009-02**: Implement `sample_departure_points()` method
3. **SUB-009-03**: Implement `compute_departure_velocity()` function
4. **SUB-009-04**: Implement grid generation with `numpy.meshgrid`
5. **SUB-009-05**: Implement parallel search with `joblib`

### New File Structure

```
e2m2e/e2m2e/transfer/
├── __init__.py                    # Update exports
├── inter_orbit.py                 # Existing class (do not modify)
├── dro_ro_search.py              # NEW: Search phase implementation
└── dro_ro_nlp.py                 # NEW: NLP optimization phase (future)
```

### Key Classes to Implement

```python
# dro_ro_search.py

@dataclass
class TransferSearchVariables:
    """转移搜索变量"""
    departure_orbit: Orbit
    departure_time_index: int
    alpha: float
    beta: float = 0.0

class DROROTransferSearch:
    """DRO到RO转移搜索算法"""
    
    def __init__(self, system: CR3BP_System, dynamics: CR3BP_Dynamics):
        ...
    
    def sample_departure_points(self, orbit: Orbit, n_points: int = 200) -> List[np.ndarray]:
        """从轨道族中等时间间隔采样"""
        ...
    
    def compute_departure_velocity(self, state: np.ndarray, alpha: float, beta: float = 0.0) -> np.ndarray:
        """根据α,β计算出发速度"""
        ...
    
    def grid_search(self, departure_orbit: Orbit, arrival_orbit: Orbit, 
                   alpha_range: Tuple[float, float],
                   beta_range: Tuple[float, float],
                   n_alpha: int = 1001,
                   n_beta: int = 101,
                   n_departure: int = 200) -> List[TransferSearchVariables]:
        """网格搜索所有转移候选"""
        ...
```
