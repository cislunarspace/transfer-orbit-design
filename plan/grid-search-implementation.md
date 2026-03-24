# Grid Search Implementation Plan

**Author**: AI Assistant  
**Date**: 2026-03-22  
**Status**: Draft  
**Replaces**: Old implementation in `e2m2e/e2m2e/transfer/dro_ro_search.py`

---

## 1. Problem Statement

The current grid search implementation in `dro_ro_search.py` has **critical bugs** that prevent correct transfer search:

### 1.1 Critical Bugs Found

| Bug | Location | Description | Impact |
|-----|----------|-------------|--------|
| **BUG-001** | `search_single_departure()` line ~380 | `departure_orbit=arrival_orbit` instead of actual departure orbit | Wrong reference orbit used |
| **BUG-002** | `compute_departure_velocity()` | α,β applied to wrong velocity component | Wrong velocity perturbation |
| **BUG-003** | Distance calculation | Nested loop O(n²) without vectorization | Very slow |
| **BUG-004** | No collision detection | Missing Earth/Moon SEC constraints | Invalid trajectories pass through |

### 1.2 Missing Features

| Feature | Priority | Description |
|---------|----------|-------------|
| **MISS-001** | P0 | t_ins calculation for insertion point |
| **MISS-002** | P0 | Velocity parallel constraint (Eq. 14) |
| **MISS-003** | P1 | Local minimum detection proper implementation |
| **MISS-004** | P1 | Intersection detection improvement |

---

## 2. Mathematical Formulation

### 2.1 Search Variables

Following paper Section III.A and Table 3:

#### Planar Transfer (2D)

| Variable | Symbol | Range | Grid Points |
|----------|--------|-------|-------------|
| Departure point | — | Equal time intervals on DRO | 200 |
| Tangential velocity ratio | α | [0.5, 2.5] | 1001 |

#### 3D Transfer

| Variable | Symbol | Range | Grid Points |
|----------|--------|-------|-------------|
| Departure point | — | Equal time intervals on DRO | 200 |
| Tangential velocity ratio | α | [0.5, 2.5] | 1001 |
| Normal velocity ratio | β | [-0.5, 0.5] | 101 |

### 2.2 Two-Impulse Transfer Model

```
Initial Orbit (DRO) ──[Δv₁ depart]──> Transfer Orbit ──[Δv₂ insert]──> Final Orbit (RO)
     x_dep                              x_i                          x_ins
```

**State vectors:**
- $x_{dep}$: Departure point state on DRO
- $x_i$: Initial state of transfer trajectory
- $x_f$: Final state of transfer trajectory  
- $x_{ins}$: Insertion point state on RO

**Velocity perturbation at departure:**

Planar Transfer:
$$
v_i = v_{dep} \cdot \alpha \quad \text{(tangential only)}
$$

3D Transfer:
$$
v_i = v_{dep} \cdot \alpha \quad \text{(tangential)} \\
v_i = v_{dep} \cdot \beta \quad \text{(normal)}
$$

**Objective function (for optimization phase):**
$$
J(y) = \Delta v_1 + \Delta v_2
$$

where:
$$
\Delta v_1 = \| \dot{x}_i - \dot{x}_{dep} \| \\
\Delta v_2 = \| \dot{x}_{ins} - \dot{x}_f \|
$$

### 2.3 Constraints (Optimization Phase)

**Position continuity (Eq. 13):**
$$
(x_f - x_{ins})^2 + (y_f - y_{ins})^2 + (z_f - z_{ins})^2 = 0
$$

**Velocity parallel (Eq. 14):**
$$
\frac{v_f \cdot v_{ins}}{\|v_f\| \|v_{ins}\|} - 1 = 0
$$

**Collision avoidance (Eq. 15-16):**
$$
r_e^2 - (x+\mu)^2 - y^2 - z^2 > 0 \quad \text{(Earth)} \\
r_m^2 - (x+\mu-1)^2 - y^2 - z^2 > 0 \quad \text{(Moon)}
$$

---

## 3. Algorithm Design

### 3.1 Planar Transfer Grid Search Algorithm

```
ALGORITHM: planar_grid_search

INPUT:
  departure_orbit: Orbit (DRO)
  arrival_orbit: Orbit (RO)
  alpha_range: (0.5, 2.5)
  n_departure: 200
  n_alpha: 101
  max_transfer_time: 15.0

OUTPUT:
  results: List[TransferSearchResult]

PROCEDURE:
1. SAMPLE departure points from departure_orbit at equal time intervals
   → departure_states[n_departure, 6]
   → departure_times[n_departure]

2. FOR EACH departure_point (x_dep, t_dep) DO
      a. Compute orbital velocity at departure: v_dep = orbit.velocity_at_time(t_dep)
      
      b. FOR alpha IN alpha_grid DO
             i.   Compute departure velocity: v_dep_new = v_dep * alpha (tangential)
             ii.  Set initial state: x_i = [x_dep, v_dep_new]
             iii. Forward integrate for max_transfer_time
             iv.  Get transfer trajectory: X_f(n_steps, 6), T_f(n_steps)
             v.   Compute min_distance to arrival_orbit
             vi.  Check intersection (distance < threshold)
             vii. Check local minimum (d'dt=0, d²/dt²>0)
             viii.IF intersection OR local_minimum THEN
                    Record result
                  END
         END
3. RETURN all results
```

### 3.2 3D Transfer Grid Search Algorithm

```
ALGORITHM: transfer_3d_grid_search

INPUT:
  departure_orbit: Orbit (DRO)
  arrival_orbit: Orbit (RO)
  alpha_range: (0.5, 2.5)
  beta_range: (-0.5, 0.5)
  n_departure: 200
  n_alpha: 101
  n_beta: 21
  max_transfer_time: 15.0

OUTPUT:
  results: List[TransferSearchResult]

PROCEDURE:
1. SAMPLE departure points from departure_orbit at equal time intervals
   → departure_states[n_departure, 6]
   → departure_times[n_departure]

2. FOR EACH departure_point (x_dep, t_dep) DO
      a. Compute orbital velocity at departure: v_dep = orbit.velocity_at_time(t_dep)
      
      b. FOR alpha IN alpha_grid DO
           FOR beta IN beta_grid DO
             i.   Compute departure velocity: v_dep_new = v_dep * alpha (tangential) + v_dep * beta (normal)
             ii.  Set initial state: x_i = [x_dep, v_dep_new]
             iii. Forward integrate for max_transfer_time
             iv.  Get transfer trajectory: X_f(n_steps, 6), T_f(n_steps)
             v.   Compute min_distance to arrival_orbit
             vi.  Check intersection (distance < threshold)
             vii. Check local minimum (d'dt=0, d²/dt²>0)
             viii.IF intersection OR local_minimum THEN
                    Record result
                  END
           END
         END
3. RETURN all results
```

### 3.3 Velocity Computation - Planar Transfer

The velocity at departure for planar transfer is computed using only the tangential direction:

```python
def compute_departure_velocity_planar(orbit_state, alpha):
    """
    Compute perturbed velocity at departure point for planar transfer.
    
    Parameters:
    -----------
    orbit_state : np.ndarray [6]
        State vector at departure [x, y, z, vx, vy, vz]
    alpha : float
        Tangential velocity ratio
    
    Returns:
    --------
    np.ndarray [3]
        Perturbed velocity vector [vx, vy, vz]
    """
    pos = orbit_state[:3]
    vel = orbit_state[3:]
    
    # Compute tangential direction (unit vector perpendicular to position in orbital plane)
    r_xy = np.sqrt(pos[0]**2 + pos[1]**2)
    if r_xy < 1e-10:
        raise ValueError("Position too close to origin")
    
    # For planar case (z=0), tangential is perpendicular to radial in xy-plane
    tangential = np.array([-pos[1], pos[0], 0]) / r_xy
    
    # Decompose velocity
    v_tangential_comp = np.dot(vel, tangential)
    
    # Perturb velocity (only tangential component)
    new_vel = vel.copy()
    new_vel += (alpha - 1.0) * v_tangential_comp * tangential
    
    return new_vel
```

### 3.4 Velocity Computation - 3D Transfer

For 3D transfer, both tangential and normal components are used:

```python
def compute_departure_velocity_3d(orbit_state, alpha, beta):
    """
    Compute perturbed velocity at departure point for 3D transfer.
    
    Parameters:
    -----------
    orbit_state : np.ndarray [6]
        State vector at departure [x, y, z, vx, vy, vz]
    alpha : float
        Tangential velocity ratio
    beta : float  
        Normal velocity ratio
    
    Returns:
    --------
    np.ndarray [3]
        Perturbed velocity vector [vx, vy, vz]
    """
    pos = orbit_state[:3]
    vel = orbit_state[3:]
    
    # Compute tangential direction
    r_xy = np.sqrt(pos[0]**2 + pos[1]**2)
    if r_xy < 1e-10:
        raise ValueError("Position too close to origin")
    
    # Tangential direction: perpendicular to position in xy-plane
    tangential = np.array([-pos[1], pos[0], 0]) / r_xy
    
    # Normal direction (out of plane)
    normal = np.array([0.0, 0.0, 1.0])
    
    # Decompose velocity
    v_tangential_comp = np.dot(vel, tangential)
    v_normal_comp = np.dot(vel, normal)
    
    # Perturb velocity (both tangential and normal components)
    new_vel = vel.copy()
    new_vel += (alpha - 1.0) * v_tangential_comp * tangential
    new_vel += beta * v_normal_comp * normal
    
    return new_vel
```

### 3.5 Distance Calculation (Vectorized)

```python
def compute_min_distance_to_orbit(trajectory_states, arrival_orbit):
    """
    Compute minimum distance from transfer trajectory to arrival orbit.
    
    Uses vectorized operations for efficiency.
    
    Parameters:
    -----------
    trajectory_states : np.ndarray [n_steps, 6]
        Transfer trajectory states
    arrival_orbit : Orbit
        Target orbit
        
    Returns:
    --------
    float
        Minimum distance
    int
        Index of minimum distance point
    """
    # Extract positions from trajectory: shape (n_steps, 3)
    traj_positions = trajectory_states[:, :3]
    
    # Get orbit positions: shape (n_orbit_states, 3)
    orbit_positions = arrival_orbit.states[:, :3]
    
    # Compute distances using broadcasting: shape (n_steps, n_orbit_states)
    # dist[i,j] = ||traj_pos[i] - orbit_pos[j]||
    diff = traj_positions[:, np.newaxis, :] - orbit_positions[np.newaxis, :, :]
    distances = np.sqrt(np.sum(diff**2, axis=2))
    
    # Find minimum
    min_idx = np.argmin(distances)
    min_distance = distances.flatten()[min_idx]
    
    # Convert flat index to (step_idx, orbit_idx)
    n_orbit = len(orbit_positions)
    step_idx = min_idx // n_orbit
    orbit_idx = min_idx % n_orbit
    
    return min_distance, step_idx, orbit_idx
```

### 3.6 Intersection Detection

```python
def detect_intersection(trajectory_states, arrival_orbit, threshold=0.001):
    """
    Detect if trajectory intersects arrival orbit.
    
    Returns:
    --------
    bool
        True if intersection found
    np.ndarray
        Intersection point state (if found)
    int
        Trajectory index at intersection
    """
    min_dist, step_idx, orbit_idx = compute_min_distance_to_orbit(
        trajectory_states, arrival_orbit
    )
    
    if min_dist < threshold:
        return True, trajectory_states[step_idx], step_idx
    return False, None, -1
```

### 3.7 Local Minimum Detection

```python
def detect_local_minimum(trajectory_states, arrival_orbit):
    """
    Detect if trajectory has local minimum distance to arrival orbit.
    
    Uses finite difference for derivative and second derivative.
    
    Returns:
    --------
    bool
        True if local minimum found
    float
        Distance at local minimum
    int
        Index of local minimum point
    """
    # Compute distance at each step
    distances = []
    orbit_positions = arrival_orbit.states[:, :3]
    
    for state in trajectory_states:
        pos = state[:3]
        diffs = pos - orbit_positions
        dists = np.sqrt(np.sum(diffs**2, axis=1))
        distances.append(np.min(dists))
    
    distances = np.array(distances)
    
    # Find local minima: d/dt = 0, d²/dt² > 0
    local_mins = []
    for i in range(1, len(distances) - 1):
        # Simple finite difference
        d1 = distances[i+1] - distances[i]     # forward diff
        d2 = distances[i] - distances[i-1]       # backward diff
        
        # Local minimum: forward diff > 0, backward diff > 0
        # Or: (dist[i+1] - dist[i]) * (dist[i] - dist[i-1]) > 0 AND dist[i+1] > dist[i] AND dist[i-1] > dist[i]
        if d1 > 0 and d2 > 0:
            local_mins.append((i, distances[i]))
    
    if local_mins:
        # Return the smallest local minimum
        best = min(local_mins, key=lambda x: x[1])
        return True, best[1], best[0]
    
    return False, np.inf, -1
```

### 3.8 Collision Detection

```python
def check_collision(trajectory_states, mu, r_earth=1-0.999, r_moon=0.999):
    """
    Check if trajectory collides with Earth or Moon.
    
    Parameters:
    -----------
    trajectory_states : np.ndarray [n_steps, 6]
        Transfer trajectory
    mu : float
        Mass ratio of CR3BP
    r_earth : float
        Earth exclusion radius (nd)
    r_moon : float  
        Moon exclusion radius (nd)
    
    Returns:
    --------
    bool
        True if collision detected
    str
        'earth' or 'moon'
    int
        Index of collision point
    """
    positions = trajectory_states[:, :3]
    
    # Earth center at (-mu, 0, 0)
    earth_center = np.array([-mu, 0.0, 0.0])
    # Moon center at (1-mu, 0, 0)
    moon_center = np.array([1.0 - mu, 0.0, 0.0])
    
    # Compute distances to centers
    dist_earth = np.linalg.norm(positions - earth_center, axis=1)
    dist_moon = np.linalg.norm(positions - moon_center, axis=1)
    
    # Check collisions
    earth_collision = np.where(dist_earth < r_earth)[0]
    moon_collision = np.where(dist_moon < r_moon)[0]
    
    if len(earth_collision) > 0:
        return True, 'earth', earth_collision[0]
    if len(moon_collision) > 0:
        return True, 'moon', moon_collision[0]
    
    return False, None, -1
```

---

## 4. Class Redesign

### 4.1 Planar Transfer Data Classes

```python
@dataclass
class PlanarTransferSearchConfig:
    """Configuration for planar transfer search."""
    # Search bounds
    alpha_min: float = 0.5
    alpha_max: float = 2.5
    n_alpha: int = 101
    
    n_departure: int = 200
    max_transfer_time: float = 15.0  # CR3BP time units
    
    # Thresholds
    intersection_threshold: float = 0.001
    min_distance_threshold: float = 0.05
    collision_earth_radius: float = 1.0 - 0.999  # Earth exclusion
    collision_moon_radius: float = 0.999         # Moon exclusion


@dataclass 
class PlanarTransferSearchResult:
    """Planar transfer search result."""
    # Search variables
    departure_orbit_name: str
    arrival_orbit_name: str
    departure_time_index: int
    alpha: float
    
    # Departure state
    departure_state: np.ndarray  # [x, y, z, vx, vy, vz]
    departure_time: float       # CR3BP time
    
    # Transfer trajectory
    transfer_trajectory: Optional[np.ndarray]  # [n_steps, 6]
    transfer_times: Optional[np.ndarray]       # [n_steps]
    transfer_time: float
    
    # Arrival intersection info
    intersection_found: bool
    intersection_point: Optional[np.ndarray]
    intersection_idx: int
    
    # Distance metrics
    min_distance: float
    min_distance_idx: int
    
    # Collision info
    collision_found: bool
    collision_body: Optional[str]  # 'earth' or 'moon'
    
    # Status
    status: str  # 'success', 'no_intersection', 'collision', 'integration_failed'
    
    @property
    def is_feasible(self) -> bool:
        """Check if result is a feasible candidate."""
        return (self.intersection_found or 
                self.min_distance < self.min_distance_threshold) and \
               not self.collision_found
```

### 4.2 3D Transfer Data Classes

```python
@dataclass
class Transfer3DSearchConfig:
    """Configuration for 3D transfer search."""
    # Search bounds
    alpha_min: float = 0.5
    alpha_max: float = 2.5
    n_alpha: int = 101
    
    beta_min: float = -0.5
    beta_max: float = 0.5
    n_beta: int = 21
    
    n_departure: int = 200
    max_transfer_time: float = 15.0  # CR3BP time units
    
    # Thresholds
    intersection_threshold: float = 0.001
    min_distance_threshold: float = 0.05
    collision_earth_radius: float = 1.0 - 0.999  # Earth exclusion
    collision_moon_radius: float = 0.999         # Moon exclusion


@dataclass 
class Transfer3DSearchResult:
    """3D transfer search result."""
    # Search variables
    departure_orbit_name: str
    arrival_orbit_name: str
    departure_time_index: int
    alpha: float
    beta: float
    
    # Departure state
    departure_state: np.ndarray  # [x, y, z, vx, vy, vz]
    departure_time: float       # CR3BP time
    
    # Transfer trajectory
    transfer_trajectory: Optional[np.ndarray]  # [n_steps, 6]
    transfer_times: Optional[np.ndarray]       # [n_steps]
    transfer_time: float
    
    # Arrival intersection info
    intersection_found: bool
    intersection_point: Optional[np.ndarray]
    intersection_idx: int
    
    # Distance metrics
    min_distance: float
    min_distance_idx: int
    
    # Collision info
    collision_found: bool
    collision_body: Optional[str]  # 'earth' or 'moon'
    
    # Status
    status: str  # 'success', 'no_intersection', 'collision', 'integration_failed'
    
    @property
    def is_feasible(self) -> bool:
        """Check if result is a feasible candidate."""
        return (self.intersection_found or 
                self.min_distance < self.min_distance_threshold) and \
               not self.collision_found
```

### 4.3 Planar Transfer Search Class

```python
class PlanarTransferSearch:
    """Planar DRO to RO transfer search algorithm."""
    
    def __init__(
        self,
        system: CR3BP_System,
        dynamics: CR3BP_Dynamics,
        config: Optional[PlanarTransferSearchConfig] = None
    ):
        self.system = system
        self.dynamics = dynamics
        self.mu = system.mu
        self.config = config or PlanarTransferSearchConfig()
    
    def sample_departure_points(self, departure_orbit: Orbit) -> Tuple[np.ndarray, np.ndarray]:
        """Sample departure points from orbit at equal time intervals."""
        n = self.config.n_departure
        times = np.linspace(0, departure_orbit.period, n, endpoint=False)
        states = np.array([departure_orbit.interpolate_at_time(t) for t in times])
        return states, times
    
    def compute_departure_velocity(self, orbit_state: np.ndarray, alpha: float) -> np.ndarray:
        """Compute perturbed velocity for planar transfer (tangential only)."""
        pos = orbit_state[:3]
        vel = orbit_state[3:]
        
        r_xy = np.sqrt(pos[0]**2 + pos[1]**2)
        if r_xy < 1e-10:
            return vel * alpha
        
        tangential = np.array([-pos[1], pos[0], 0]) / r_xy
        v_tangential_comp = np.dot(vel, tangential)
        
        new_vel = vel.copy()
        new_vel += (alpha - 1.0) * v_tangential_comp * tangential
        
        return new_vel
    
    def forward_integrate(
        self,
        initial_state: np.ndarray,
        transfer_time: float,
        dt: float = 0.001
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Forward integrate transfer trajectory."""
        ...
    
    def compute_min_distance(
        self,
        trajectory_states: np.ndarray,
        arrival_orbit: Orbit
    ) -> Tuple[float, int]:
        """Compute minimum distance from trajectory to arrival orbit."""
        ...
    
    def detect_intersection(
        self,
        trajectory_states: np.ndarray,
        arrival_orbit: Orbit
    ) -> Tuple[bool, np.ndarray, int]:
        """Detect intersection with arrival orbit."""
        ...
    
    def detect_local_minimum(
        self,
        trajectory_states: np.ndarray,
        arrival_orbit: Orbit
    ) -> Tuple[bool, float, int]:
        """Detect local minimum distance to arrival orbit."""
        ...
    
    def check_collision(self, trajectory_states: np.ndarray) -> Tuple[bool, Optional[str], int]:
        """Check for Earth/Moon collision."""
        ...
    
    def search_single_departure(
        self,
        departure_state: np.ndarray,
        departure_time: float,
        arrival_orbit: Orbit
    ) -> List[PlanarTransferSearchResult]:
        """Search over alpha grid for one departure point."""
        ...
    
    def grid_search(
        self,
        departure_orbit: Orbit,
        arrival_orbit: Orbit,
        verbose: bool = True
    ) -> List[PlanarTransferSearchResult]:
        """Main grid search over all departure points."""
        ...
```

### 4.4 3D Transfer Search Class

```python
class Transfer3DSearch:
    """3D DRO to RO transfer search algorithm."""
    
    def __init__(
        self,
        system: CR3BP_System,
        dynamics: CR3BP_Dynamics,
        config: Optional[Transfer3DSearchConfig] = None
    ):
        self.system = system
        self.dynamics = dynamics
        self.mu = system.mu
        self.config = config or Transfer3DSearchConfig()
    
    def sample_departure_points(self, departure_orbit: Orbit) -> Tuple[np.ndarray, np.ndarray]:
        """Sample departure points from orbit at equal time intervals."""
        n = self.config.n_departure
        times = np.linspace(0, departure_orbit.period, n, endpoint=False)
        states = np.array([departure_orbit.interpolate_at_time(t) for t in times])
        return states, times
    
    def compute_departure_velocity(
        self, 
        orbit_state: np.ndarray, 
        alpha: float, 
        beta: float
    ) -> np.ndarray:
        """Compute perturbed velocity for 3D transfer (tangential + normal)."""
        pos = orbit_state[:3]
        vel = orbit_state[3:]
        
        r_xy = np.sqrt(pos[0]**2 + pos[1]**2)
        if r_xy < 1e-10:
            return vel * alpha
        
        tangential = np.array([-pos[1], pos[0], 0]) / r_xy
        normal = np.array([0.0, 0.0, 1.0])
        
        v_tangential_comp = np.dot(vel, tangential)
        v_normal_comp = np.dot(vel, normal)
        
        new_vel = vel.copy()
        new_vel += (alpha - 1.0) * v_tangential_comp * tangential
        new_vel += beta * v_normal_comp * normal
        
        return new_vel
    
    def forward_integrate(
        self,
        initial_state: np.ndarray,
        transfer_time: float,
        dt: float = 0.001
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Forward integrate transfer trajectory."""
        ...
    
    def compute_min_distance(
        self,
        trajectory_states: np.ndarray,
        arrival_orbit: Orbit
    ) -> Tuple[float, int]:
        """Compute minimum distance from trajectory to arrival orbit."""
        ...
    
    def detect_intersection(
        self,
        trajectory_states: np.ndarray,
        arrival_orbit: Orbit
    ) -> Tuple[bool, np.ndarray, int]:
        """Detect intersection with arrival orbit."""
        ...
    
    def detect_local_minimum(
        self,
        trajectory_states: np.ndarray,
        arrival_orbit: Orbit
    ) -> Tuple[bool, float, int]:
        """Detect local minimum distance to arrival orbit."""
        ...
    
    def check_collision(self, trajectory_states: np.ndarray) -> Tuple[bool, Optional[str], int]:
        """Check for Earth/Moon collision."""
        ...
    
    def search_single_departure(
        self,
        departure_state: np.ndarray,
        departure_time: float,
        arrival_orbit: Orbit
    ) -> List[Transfer3DSearchResult]:
        """Search over alpha, beta grid for one departure point."""
        ...
    
    def grid_search(
        self,
        departure_orbit: Orbit,
        arrival_orbit: Orbit,
        verbose: bool = True
    ) -> List[Transfer3DSearchResult]:
        """Main grid search over all departure points."""
        ...
```

---

## 5. Implementation Sequence

### Planar Transfer Implementation

| Step | Task | Priority | Estimated Time |
|------|------|----------|----------------|
| 1 | Create `PlanarTransferSearchConfig` dataclass | P0 | 30 min |
| 2 | Create `PlanarTransferSearchResult` dataclass | P0 | 30 min |
| 3 | Implement `sample_departure_points()` | P0 | 1 hour |
| 4 | Implement `compute_departure_velocity_planar()` | P0 | 2 hours |
| 5 | Implement `forward_integrate()` using e2m2e dynamics | P0 | 2 hours |
| 6 | Implement vectorized `compute_min_distance()` | P0 | 1 hour |
| 7 | Implement `detect_intersection()` | P0 | 1 hour |
| 8 | Implement `detect_local_minimum()` | P0 | 2 hours |
| 9 | Implement `check_collision()` | P0 | 1 hour |
| 10 | Implement `search_single_departure()` | P0 | 2 hours |
| 11 | Implement `grid_search()` orchestration | P0 | 1 hour |
| 12 | Write unit tests for planar | P0 | 4 hours |
| 13 | Integration test with planar orbits | P1 | 2 hours |

### 3D Transfer Implementation

| Step | Task | Priority | Estimated Time |
|------|------|----------|----------------|
| 14 | Create `Transfer3DSearchConfig` dataclass | P0 | 30 min |
| 15 | Create `Transfer3DSearchResult` dataclass | P0 | 30 min |
| 16 | Implement `compute_departure_velocity_3d()` | P0 | 2 hours |
| 17 | Write unit tests for 3D | P0 | 4 hours |
| 18 | Integration test with 3D orbits | P1 | 2 hours |

---

## 6. Test Cases

### 6.1 Planar Transfer Unit Tests

```python
# tests/test_transfer/test_planar_search.py

class TestPlanarTransferSearchConfig:
    """Test PlanarTransferSearchConfig dataclass."""
    
    def test_default_values(self):
        config = PlanarTransferSearchConfig()
        assert config.alpha_min == 0.5
        assert config.alpha_max == 2.5
        assert config.n_alpha == 101
        assert config.n_beta is None
        # ...
    
    def test_custom_values(self):
        config = PlanarTransferSearchConfig(
            alpha_min=0.8,
            alpha_max=1.5,
            n_alpha=50
        )
        assert config.alpha_min == 0.8
        assert config.n_alpha == 50


class TestComputeDepartureVelocityPlanar:
    """Test planar velocity computation."""
    
    def test_alpha_1_returns_original_velocity(self):
        """When alpha=1, velocity should be unchanged."""
        state = np.array([1.0, 0.0, 0.0, 0.0, 1.0, 0.0])  # Circular orbit velocity
        search = PlanarTransferSearch(...)
        
        new_vel = search.compute_departure_velocity(state, alpha=1.0)
        
        np.testing.assert_allclose(new_vel, state[3:], rtol=1e-10)
    
    def test_alpha_2_doubles_tangential_velocity(self):
        """When alpha=2, tangential velocity should double."""
        state = np.array([1.0, 0.0, 0.0, 0.0, 1.0, 0.0])
        search = PlanarTransferSearch(...)
        
        new_vel = search.compute_departure_velocity(state, alpha=2.0)
        
        original_tangential = 1.0
        assert new_vel[1] == pytest.approx(2.0 * original_tangential)


class TestComputeMinDistance:
    """Test minimum distance computation."""
    
    def test_identical_trajectories(self):
        """Zero distance for same trajectory."""
        trajectory = np.array([[1, 0, 0], [0, 1, 0], [0, 0, 1]])
        orbit = create_dummy_orbit(trajectory)
        
        search = PlanarTransferSearch(...)
        min_dist, idx = search.compute_min_distance(trajectory, orbit)
        
        assert min_dist == pytest.approx(0.0, abs=1e-10)
    
    def test_known_distance(self):
        """Known distance between two points."""
        trajectory = np.array([[0, 0, 0], [1, 0, 0]])
        orbit_positions = np.array([[0, 0, 0], [3, 0, 0]])
        orbit = create_dummy_orbit(orbit_positions)
        
        search = PlanarTransferSearch(...)
        min_dist, idx = search.compute_min_distance(trajectory, orbit)
        
        assert min_dist == pytest.approx(0.0, abs=1e-10)


class TestCollisionDetection:
    """Test Earth/Moon collision detection."""
    
    def test_earth_collision_detected(self):
        """Should detect trajectory passing through Earth."""
        trajectory = np.array([[-1.0, 0, 0], [-0.99, 0, 0]])
        
        search = PlanarTransferSearch(...)
        collision, body, idx = search.check_collision(trajectory)
        
        assert collision is True
        assert body == 'earth'
    
    def test_no_collision_in_valid_trajectory(self):
        """Valid trajectory should not trigger collision."""
        trajectory = np.array([[1.1, 0, 0], [1.2, 0.1, 0]])
        
        search = PlanarTransferSearch(...)
        collision, body, idx = search.check_collision(trajectory)
        
        assert collision is False
```

### 6.2 Planar Transfer Integration Test

```python
class TestPlanarGridSearchIntegration:
    """Integration test with actual DRO and RO orbits."""
    
    def test_dro_to_ro_planar_transfer_search(self):
        """Test full grid search on DRO to RO planar transfer."""
        dro = load_orbit("output/dro/dro_31_3857029796.json")
        ro = load_orbit("output/ro/ro_31_3857030320.json")
        
        system = CR3BP_System(mu=1.21506683e-2)
        dynamics = CR3BP_Dynamics(system)
        search = PlanarTransferSearch(system, dynamics)
        
        config = PlanarTransferSearchConfig(n_departure=10, n_alpha=11)
        search.config = config
        
        results = search.grid_search(dro, ro)
        
        assert len(results) > 0
        feasible = [r for r in results if r.is_feasible]
        assert len(feasible) > 0
```

### 6.3 3D Transfer Unit Tests

```python
# tests/test_transfer/test_3d_search.py

class TestTransfer3DSearchConfig:
    """Test Transfer3DSearchConfig dataclass."""
    
    def test_default_values(self):
        config = Transfer3DSearchConfig()
        assert config.alpha_min == 0.5
        assert config.alpha_max == 2.5
        assert config.n_alpha == 101
        assert config.beta_min == -0.5
        assert config.beta_max == 0.5
        assert config.n_beta == 21
        # ...
    
    def test_custom_values(self):
        config = Transfer3DSearchConfig(
            alpha_min=0.8,
            alpha_max=1.5,
            n_alpha=50,
            beta_min=-0.3,
            beta_max=0.3,
            n_beta=11
        )
        assert config.alpha_min == 0.8
        assert config.n_alpha == 50
        assert config.beta_min == -0.3
        assert config.n_beta == 11


class TestComputeDepartureVelocity3D:
    """Test 3D velocity computation."""
    
    def test_alpha_1_beta_0_returns_original_velocity(self):
        """When alpha=1 and beta=0, velocity should be unchanged."""
        state = np.array([1.0, 0.0, 0.0, 0.0, 1.0, 0.0])
        search = Transfer3DSearch(...)
        
        new_vel = search.compute_departure_velocity(state, alpha=1.0, beta=0.0)
        
        np.testing.assert_allclose(new_vel, state[3:], rtol=1e-10)
    
    def test_beta_affects_normal_velocity(self):
        """When beta!=0, normal velocity component should change."""
        state = np.array([1.0, 0.0, 0.0, 0.0, 1.0, 0.5])
        search = Transfer3DSearch(...)
        
        new_vel = search.compute_departure_velocity(state, alpha=1.0, beta=1.0)
        
        # z-component should be affected by beta
        assert new_vel[2] != state[5]


class Test3DGridSearchIntegration:
    """Integration test with 3D orbits."""
    
    def test_dro_to_3d_ro_transfer_search(self):
        """Test full grid search on DRO to 3D RO."""
        dro = load_orbit("output/dro/dro_31_3857029796.json")
        ro_3d = load_orbit("output/ro/ro_3d_*.json")
        
        system = CR3BP_System(mu=1.21506683e-2)
        dynamics = CR3BP_Dynamics(system)
        search = Transfer3DSearch(system, dynamics)
        
        config = Transfer3DSearchConfig(n_departure=10, n_alpha=11, n_beta=3)
        search.config = config
        
        results = search.grid_search(dro, ro_3d)
        
        assert len(results) > 0
        feasible = [r for r in results if r.is_feasible]
        assert len(feasible) > 0
```

---

## 7. File Structure

```
e2m2e/e2m2e/transfer/
├── __init__.py
├── dro_ro_search.py          # Original (keep for reference)
├── planar_transfer_search.py # NEW: Planar transfer implementation
├── transfer_3d_search.py     # NEW: 3D transfer implementation
└── dro_ro_nlp.py             # Existing NLP module

tests/e2m2e/test_transfer/
├── __init__.py
├── test_planar_search.py     # NEW: Planar transfer unit tests
├── test_3d_search.py         # NEW: 3D transfer unit tests
└── conftest.py               # Shared fixtures
```

---

## 8. Migration Path

1. **Phase 1**: Create `planar_transfer_search.py` and `transfer_3d_search.py`
2. **Phase 2**: Run existing tests against new implementations
3. **Phase 3**: Update `grid_search.py` to use new classes
4. **Phase 4**: Once validated, deprecate old `dro_ro_search.py`

---

## 9. References

- Cui et al. (2025) Section III.A "Search Phase"
- Table 3: Search variable bounds
- Eq. 13-17: Constraints for optimization phase
