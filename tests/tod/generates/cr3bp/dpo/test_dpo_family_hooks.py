"""Tests for DpoFamilyGenerator hook decomposition.

Verify DPO family generator implements family-specific logic through
base class hooks, not overriding run().
"""

# pyright: reportOptionalMemberAccess=false

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from tod.generates.cr3bp._family_pipeline import FamilyGeneratorConfig
from tod.generates.cr3bp.dpo.generate_dpo_family import DpoFamilyGenerator


# ---------------------------------------------------------------------------
# Helper fixtures
# ---------------------------------------------------------------------------


def _make_dpo_gen() -> DpoFamilyGenerator:
    """Construct a DpoFamilyGenerator instance (without runtime state)."""
    config = FamilyGeneratorConfig(
        family_type="dpo",
        output_subdir="dpo",
    )
    return DpoFamilyGenerator(config)


def _make_dpo_args(**overrides) -> MagicMock:
    """Construct mock DPO CLI args with DPO-specific defaults."""
    args = MagicMock()
    args.x0 = overrides.get("x0", 1.03774)
    args.vy0 = overrides.get("vy0", 0.503284)
    args.period = overrides.get("period", 1.2011)
    args.param_min = overrides.get("param_min", 0.997)
    args.param_max = overrides.get("param_max", 1.046)
    args.step_size = overrides.get("step_size", 0.001)
    args.verbose = overrides.get("verbose", False)
    args.output_dir = overrides.get("output_dir", None)
    args.log_level = overrides.get("log_level", "WARNING")
    args.n_milestones = overrides.get("n_milestones", 5)
    return args


# ---------------------------------------------------------------------------
# 1. _setup_corrector — x0 fixed 2D symmetric correction
# ---------------------------------------------------------------------------


class TestSetupCorrector:
    """Verify _setup_corrector creates corrector with setup_2D_symmetric_x_fixed_x0."""

    def test_calls_setup_with_x0(self):
        """DPO corrector must use setup_2D_symmetric_x_fixed_x0 with args.x0."""
        gen = _make_dpo_gen()
        args = _make_dpo_args(x0=1.03774)

        with patch("tod.generates.cr3bp.dpo.generate_dpo_family.e2m2e.algorithms.DifferentialCorrection") as MockDC:
            mock_corrector = MagicMock()
            MockDC.return_value = mock_corrector

            result = gen._setup_corrector(args)

            MockDC.assert_called_once()
            mock_corrector.setup_2D_symmetric_x_fixed_x0.assert_called_once_with(
                x0=1.03774,
            )
            assert result is mock_corrector

    def test_different_x0_value(self):
        """Corrector setup uses whatever x0 is in args."""
        gen = _make_dpo_gen()
        args = _make_dpo_args(x0=1.02)

        with patch("tod.generates.cr3bp.dpo.generate_dpo_family.e2m2e.algorithms.DifferentialCorrection") as MockDC:
            mock_corrector = MagicMock()
            MockDC.return_value = mock_corrector

            gen._setup_corrector(args)

            mock_corrector.setup_2D_symmetric_x_fixed_x0.assert_called_once_with(
                x0=1.02,
            )


# ---------------------------------------------------------------------------
# 2. _get_seed_orbit — [x0, 0, 0, 0, vy0, 0] state construction
# ---------------------------------------------------------------------------


class TestGetSeedOrbit:
    """Verify _get_seed_orbit constructs [x0, 0, 0, 0, vy0, 0] state and sets period."""

    def test_constructs_planar_symmetric_state(self):
        """DPO seed is planar (y=z=vx=vz=0) with positive vy0."""
        gen = _make_dpo_gen()
        args = _make_dpo_args(x0=1.03774, vy0=0.503284, period=1.2011)

        seed = gen._get_seed_orbit(args)

        state = list(seed.states[0])
        assert state == [1.03774, 0.0, 0.0, 0.0, 0.503284, 0.0]
        assert seed.period == 1.2011

    def test_positive_vy0(self):
        """DPO initial vy0 must be positive."""
        gen = _make_dpo_gen()
        args = _make_dpo_args(vy0=0.503284)

        seed = gen._get_seed_orbit(args)

        assert seed.states[0][4] > 0

    def test_period_is_set(self):
        """Seed orbit period must equal args.period."""
        gen = _make_dpo_gen()
        args = _make_dpo_args(period=1.5)

        seed = gen._get_seed_orbit(args)

        assert seed.period == 1.5


# ---------------------------------------------------------------------------
# 3. _run_continuation — natural_continuation call
# ---------------------------------------------------------------------------


class TestRunContinuation:
    """Verify _run_continuation calls natural_continuation with correct params."""

    def test_calls_natural_continuation_with_param_range_and_step_size(self):
        """Continuation uses param_range=(param_min, param_max) and step_size."""
        gen = _make_dpo_gen()
        args = _make_dpo_args(param_min=0.997, param_max=1.046, step_size=0.001)

        mock_seed = MagicMock()
        mock_seed.states = np.array([[1.03774, 0.0, 0.0, 0.0, 0.503284, 0.0]])

        with patch("tod.generates.cr3bp.dpo.generate_dpo_family.e2m2e.algorithms.Continuation") as MockCont:
            mock_family = MagicMock()
            mock_family.orbits = []
            mock_cont_instance = MagicMock()
            mock_cont_instance.natural_continuation.return_value = mock_family
            MockCont.return_value = mock_cont_instance

            result = gen._run_continuation(MagicMock(), mock_seed, args)

        call_kwargs = mock_cont_instance.natural_continuation.call_args
        assert call_kwargs.kwargs["param_range"] == (0.997, 1.046)
        assert call_kwargs.kwargs["step_size"] == 0.001
        assert call_kwargs.kwargs["seed_orbit"] is mock_seed
        assert result is mock_family

    def test_passes_verbose_flag(self):
        """Verbose flag is forwarded to natural_continuation."""
        gen = _make_dpo_gen()
        args = _make_dpo_args(verbose=True)

        mock_seed = MagicMock()
        mock_seed.states = np.array([[1.03774, 0.0, 0.0, 0.0, 0.503284, 0.0]])

        with patch("tod.generates.cr3bp.dpo.generate_dpo_family.e2m2e.algorithms.Continuation") as MockCont:
            mock_family = MagicMock()
            mock_family.orbits = []
            mock_cont_instance = MagicMock()
            mock_cont_instance.natural_continuation.return_value = mock_family
            MockCont.return_value = mock_cont_instance

            gen._run_continuation(MagicMock(), mock_seed, args)

        call_kwargs = mock_cont_instance.natural_continuation.call_args
        assert call_kwargs.kwargs["verbose"] is True


# ---------------------------------------------------------------------------
# 4. argparse — removed params not accepted
# ---------------------------------------------------------------------------


class TestArgparseNoRemovedParams:
    """Verify --method and --n-orbits are not accepted by argparse."""

    def test_method_not_accepted(self):
        """--method should not be accepted by argparse."""
        with pytest.raises(SystemExit):
            DpoFamilyGenerator.build_parser("test").parse_args(["--method", "pseudo_arclength"])

    def test_n_orbits_not_accepted(self):
        """--n-orbits should not be accepted by argparse."""
        with pytest.raises(SystemExit):
            DpoFamilyGenerator.build_parser("test").parse_args(["--n-orbits", "20"])
