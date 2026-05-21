"""Regression tests for 3D view bounds calculation.

Ensures that auto-computed center/radius contain the orbit data,
regardless of whether it is an L1, L2, or L3 family.
"""

import numpy as np
import pytest

from tod.plot.family_plot_orchestrator import compute_view_bounds


def _make_fake_orbit_states(x_center: float, y_center: float, z_center: float) -> np.ndarray:
    t = np.linspace(0, 2 * np.pi, 100)
    x = x_center + 0.1 * np.cos(t)
    y = y_center + 0.05 * np.sin(t)
    z = z_center + 0.2 * np.sin(2 * t)
    return np.column_stack([x, y, z, np.zeros_like(x), np.zeros_like(x), np.zeros_like(x)])


class TestComputeViewBounds:
    @pytest.mark.parametrize(
        "x_center,y_center,z_center",
        [
            (0.85, 0.0, 0.0),
            (1.15, 0.0, 0.0),
            (-1.0, 0.0, 0.0),
        ],
    )
    def test_bounds_contain_orbit(self, x_center: float, y_center: float, z_center: float) -> None:
        states = _make_fake_orbit_states(x_center, y_center, z_center)
        xlim_2d, ylim_2d, center_3d, radius_3d = compute_view_bounds(states)

        x_min, x_max = states[:, 0].min(), states[:, 0].max()
        y_min, y_max = states[:, 1].min(), states[:, 1].max()
        z_min, z_max = states[:, 2].min(), states[:, 2].max()

        assert x_min >= center_3d[0] - radius_3d
        assert x_max <= center_3d[0] + radius_3d
        assert y_min >= center_3d[1] - radius_3d
        assert y_max <= center_3d[1] + radius_3d
        assert z_min >= center_3d[2] - radius_3d
        assert z_max <= center_3d[2] + radius_3d

    def test_hardcoded_l1_center_misses_l3(self) -> None:
        states = _make_fake_orbit_states(-1.0, 0.0, 0.0)
        x_min, x_max = states[:, 0].min(), states[:, 0].max()

        old_center = 0.9
        old_radius = 0.4
        old_xlim = (old_center - old_radius, old_center + old_radius)

        assert x_min < old_xlim[0] or x_max > old_xlim[1], (
            "L3 orbit should fall outside the old hard-coded L1 view"
        )

    def test_2d_bounds_are_reasonable(self) -> None:
        states = _make_fake_orbit_states(0.85, 0.0, 0.1)
        xlim_2d, ylim_2d, _, _ = compute_view_bounds(states)

        assert xlim_2d[0] < xlim_2d[1]
        assert ylim_2d[0] < ylim_2d[1]
        assert xlim_2d[1] - xlim_2d[0] > 0.1
        assert ylim_2d[1] - ylim_2d[0] > 0.1
