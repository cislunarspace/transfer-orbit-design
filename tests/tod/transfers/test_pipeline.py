"""Unit tests for tod.transfers._pipeline shared module."""

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

from tod.transfers import _pipeline


# =============================================================================
# build_cr3bp_dynamics
# =============================================================================


class TestBuildCr3bpDynamics:
    def test_returns_system_and_dynamics(self):
        system, dynamics = _pipeline.build_cr3bp_dynamics()
        from e2m2e.core import CR3BP_Dynamics, CR3BP_System

        assert isinstance(system, CR3BP_System)
        assert isinstance(dynamics, CR3BP_Dynamics)

    def test_default_integrator_is_dop853(self):
        _, dynamics = _pipeline.build_cr3bp_dynamics()
        assert dynamics.integrator == "DOP853"

    def test_default_tolerances(self):
        _, dynamics = _pipeline.build_cr3bp_dynamics()
        assert dynamics.rtol == 1e-12
        assert dynamics.atol == 1e-12

    def test_custom_parameters(self):
        system, dynamics = _pipeline.build_cr3bp_dynamics(
            mu=0.3,
            integrator="RK45",
            rtol=1e-8,
            atol=1e-9,
            max_step=0.01,
        )
        assert system.mu == 0.3
        assert dynamics.integrator == "RK45"
        assert dynamics.rtol == 1e-8
        assert dynamics.atol == 1e-9
        assert dynamics.max_step == 0.01


# =============================================================================
# json_safe
# =============================================================================


class TestJsonSafe:
    def test_none_passthrough(self):
        assert _pipeline.json_safe(None) is None

    def test_scalar_passthrough(self):
        assert _pipeline.json_safe(42) == 42
        assert _pipeline.json_safe(3.14) == 3.14
        assert _pipeline.json_safe("hello") == "hello"
        assert _pipeline.json_safe(True) is True

    def test_numpy_scalar_conversion(self):
        assert _pipeline.json_safe(np.float64(3.14)) == 3.14
        assert isinstance(_pipeline.json_safe(np.float64(3.14)), float)
        assert _pipeline.json_safe(np.int64(42)) == 42
        assert isinstance(_pipeline.json_safe(np.int64(42)), int)
        assert _pipeline.json_safe(np.bool_(True)) is True

    def test_numpy_array_conversion(self):
        arr = np.array([1.0, 2.0, 3.0])
        result = _pipeline.json_safe(arr)
        assert result == [1.0, 2.0, 3.0]
        assert isinstance(result, list)

    def test_nested_dict(self):
        data = {"a": np.float64(1.0), "b": {"c": np.array([2, 3])}}
        result = _pipeline.json_safe(data)
        assert result == {"a": 1.0, "b": {"c": [2, 3]}}
        # Verify it's JSON-serializable
        json.dumps(result)

    def test_nested_list(self):
        data = [np.float64(1), [np.array([2, 3])]]
        result = _pipeline.json_safe(data)
        # np.float64 → float (1.0), np.array → list inside nested list → [[2,3]]
        assert result == [1.0, [[2, 3]]]
        json.dumps(result)

    def test_tuple_conversion(self):
        data = (np.float64(1), np.float64(2))
        result = _pipeline.json_safe(data)
        assert result == [1, 2]

    def test_empty_structures(self):
        assert _pipeline.json_safe({}) == {}
        assert _pipeline.json_safe([]) == []
        arr = np.array([])
        assert _pipeline.json_safe(arr) == []


# =============================================================================
# serialize_nlp_result
# =============================================================================


class _FakeTransferType(Enum):
    DIRECT = "DIRECT"
    EXTERNAL = "EXTERNAL"
    LGA = "LGA"


@dataclass
class _FakeNLPOptimizationResult:
    success: bool = True
    alpha: float = 1.5
    transfer_time: float = 10.0
    t_ins: float = 2.0
    objective_value: float = 0.5
    delta_v1: float = 0.3
    delta_v2: float = 0.2
    message: str = "OK"
    constraints_violation: dict | None = None
    transfer_type: _FakeTransferType | None = None


class TestSerializeNlpResult:
    def test_basic_serialization(self):
        res = _FakeNLPOptimizationResult(
            constraints_violation={"position": 1e-6},
            transfer_type=_FakeTransferType.DIRECT,
        )
        result = _pipeline.serialize_nlp_result(res)
        assert result["success"] is True
        assert result["alpha"] == 1.5
        assert result["transfer_time"] == 10.0
        assert result["t_ins"] == 2.0
        assert result["objective_value"] == 0.5
        assert result["delta_v1"] == 0.3
        assert result["delta_v2"] == 0.2
        assert result["message"] == "OK"
        assert result["transfer_type"] == "DIRECT"

    def test_constraints_violation_floats(self):
        res = _FakeNLPOptimizationResult(
            constraints_violation={"position": np.float64(1e-6)}
        )
        result = _pipeline.serialize_nlp_result(res)
        assert isinstance(result["constraints_violation"]["position"], float)

    def test_none_constraints(self):
        res = _FakeNLPOptimizationResult(constraints_violation=None)
        result = _pipeline.serialize_nlp_result(res)
        assert result["constraints_violation"] == {}

    def test_none_transfer_type(self):
        res = _FakeNLPOptimizationResult(transfer_type=None)
        result = _pipeline.serialize_nlp_result(res)
        assert result["transfer_type"] is None

    def test_no_t_ins_attribute(self):
        """Handle NLPOptimizationResult without t_ins (older e2m2e versions)."""
        res = MagicMock()
        res.success = False
        res.alpha = 0.0
        res.transfer_time = 0.0
        res.objective_value = 0.0
        res.delta_v1 = 0.0
        res.delta_v2 = 0.0
        res.message = "failed"
        res.constraints_violation = None
        res.transfer_type = None
        del res.t_ins  # simulate missing attribute

        result = _pipeline.serialize_nlp_result(res)
        assert result["t_ins"] is None

    def test_json_serializable(self):
        res = _FakeNLPOptimizationResult(
            constraints_violation={"position": 1e-6, "velocity": 1e-8},
            transfer_type=_FakeTransferType.EXTERNAL,
        )
        result = _pipeline.serialize_nlp_result(res)
        json.dumps(result)  # should not raise


# =============================================================================
# load_search_results
# =============================================================================


class TestLoadSearchResults:
    def test_loads_json_file(self, tmp_path: Path):
        data = [{"alpha": 1.0, "is_feasible": True}, {"alpha": 2.0, "is_feasible": False}]
        filepath = tmp_path / "search.json"
        filepath.write_text(json.dumps(data), encoding="utf-8")

        result = _pipeline.load_search_results(filepath)
        assert result == data

    def test_raises_on_missing_file(self, tmp_path: Path):
        filepath = tmp_path / "nonexistent.json"
        with pytest.raises(FileNotFoundError):
            _pipeline.load_search_results(filepath)


# =============================================================================
# find_project_root
# =============================================================================


class TestFindProjectRoot:
    def test_returns_existing_directory(self):
        root = _pipeline.find_project_root()
        assert root.is_dir()

    def test_contains_pyproject_toml(self):
        root = _pipeline.find_project_root()
        assert (root / "pyproject.toml").is_file()


# =============================================================================
# inject_debug_args
# =============================================================================


class TestInjectDebugArgs:
    def test_injects_when_no_args(self):
        argv = ["script.py"]
        _pipeline.inject_debug_args(argv, ["--alpha-min", "0.5", "--n-departure", "200"])
        assert argv == ["script.py", "--alpha-min", "0.5", "--n-departure", "200"]

    def test_no_inject_when_args_present(self):
        argv = ["script.py", "--alpha-min", "1.0"]
        _pipeline.inject_debug_args(argv, ["--alpha-min", "0.5"])
        assert argv == ["script.py", "--alpha-min", "1.0"]

    def test_no_inject_when_empty_defaults(self):
        argv = ["script.py"]
        _pipeline.inject_debug_args(argv, [])
        assert argv == ["script.py"]

    def test_empty_argv(self):
        argv: list[str] = []
        _pipeline.inject_debug_args(argv, ["--flag"])
        # len(argv)==0, so no injection
        assert argv == []


# =============================================================================
# apply_default_blas_env
# =============================================================================


class TestApplyDefaultBlasEnv:
    def test_sets_blas_env_vars(self, monkeypatch):
        # Remove any pre-existing BLAS env vars
        for key in [
            "OMP_NUM_THREADS",
            "MKL_NUM_THREADS",
            "OPENBLAS_NUM_THREADS",
            "GOTO_NUM_THREADS",
            "VECLIB_MAXIMUM_THREADS",
            "NUMEXPR_NUM_THREADS",
        ]:
            monkeypatch.delenv(key, raising=False)

        _pipeline.apply_default_blas_env()

        import os

        assert os.environ.get("OMP_NUM_THREADS") == "1"
        assert os.environ.get("MKL_NUM_THREADS") == "1"


# =============================================================================
# TransferSearchConfig / TransferOptimizeConfig dataclasses
# =============================================================================


class TestTransferSearchConfig:
    def test_default_values(self):
        cfg = _pipeline.TransferSearchConfig()
        assert cfg.integrator == "DOP853"
        assert cfg.rtol == 1e-12
        assert cfg.atol == 1e-12
        assert cfg.n_departure == 200
        assert cfg.n_alpha == 100

    def test_override_values(self):
        cfg = _pipeline.TransferSearchConfig(
            n_departure=500,
            alpha_min=1.0,
            alpha_max=3.0,
        )
        assert cfg.n_departure == 500
        assert cfg.alpha_min == 1.0
        assert cfg.alpha_max == 3.0
        # Unchanged defaults
        assert cfg.integrator == "DOP853"


class TestTransferOptimizeConfig:
    def test_default_values(self):
        cfg = _pipeline.TransferOptimizeConfig()
        assert cfg.integrator == "DOP853"
        assert cfg.nlp_maxiter == 100
        assert cfg.nlp_ftol == 1e-6
        assert cfg.use_relaxed_velocity is True

    def test_override_values(self):
        cfg = _pipeline.TransferOptimizeConfig(
            nlp_maxiter=200,
            use_copt=True,
            n_workers=4,
        )
        assert cfg.nlp_maxiter == 200
        assert cfg.use_copt is True
        assert cfg.n_workers == 4
