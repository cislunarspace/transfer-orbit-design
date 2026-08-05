"""tests for persistence ephemeris arrays + save_control_result (issue #348)。"""

from __future__ import annotations

import json
import re

import numpy as np
import pytest

from src.engine.facade_bridge import ControlResultData, OrbitDesignResultData
from src.engine.persistence import load_artifact_arrays, save_artifact, save_control_result
from src.model.discovery import discover_artifacts

_RNG = np.random.default_rng(seed=42)


def _make_dto_with_ephemeris(n: int = 100) -> OrbitDesignResultData:
    return OrbitDesignResultData(
        orbit_type="DRO",
        epoch_utc="2024-01-01T00:00:00",
        duration_day=365.25,
        initial_state=np.array([1.0, 2.0, 3.0, 0.1, 0.2, 0.3]),
        cr3bp_jacobi=3.0058,
        states=_RNG.standard_normal((n, 6)),
        times=np.linspace(0, 365.25, n),
        correction_converged=True,
        correction_iterations=3,
        mu=0.012153645822478,
        ephemeris={
            "year": np.full(n, 2024),
            "month": np.ones(n, dtype=int),
            "day": np.ones(n, dtype=int),
            "hour": np.zeros(n, dtype=int),
            "minute": np.zeros(n, dtype=int),
            "second": np.zeros(n, dtype=float),
            "position_km": _RNG.standard_normal((n, 3)),
            "velocity_mps": _RNG.standard_normal((n, 3)),
            "synodic_position": _RNG.standard_normal((n, 3)),
            "times_jd_tdb": None,
        },
    )


def _make_control_result(n: int = 50) -> ControlResultData:
    return ControlResultData(
        num_failed=1,
        sk_statistic_rows=np.array([[1.0, 2.0, 3.0]]),
        maneuvers_mjd_tdb=np.array([60000.0, 60030.0]),
        maneuvers_delta_v_mps=np.array([0.5, 0.3]),
        controlled_states=_RNG.standard_normal((n, 6)),
        controlled_times=np.arange(n),
        mu=0.012153645822478,
    )


class TestSaveArtifactEphemeris:
    def test_save_artifact_npz_contains_ephemeris_arrays(self, tmp_path):
        """NPZ 应含 eph_position_km / eph_year 等键。"""
        dto = _make_dto_with_ephemeris()
        _, npz_path = save_artifact(dto, tmp_path)
        with np.load(npz_path) as data:
            assert "eph_position_km" in data
            assert "eph_year" in data
            assert "eph_synodic_position" in data
            np.testing.assert_array_equal(data["eph_position_km"], dto.ephemeris["position_km"])

    def test_save_artifact_skips_none_ephemeris_values(self, tmp_path):
        """times_jd_tdb=None 不应出现在 NPZ 中。"""
        dto = _make_dto_with_ephemeris()
        _, npz_path = save_artifact(dto, tmp_path)
        with np.load(npz_path) as data:
            assert "eph_times_jd_tdb" not in data.files

    def test_save_artifact_json_has_ephemeris_flag(self, tmp_path):
        """JSON 元数据应含 has_ephemeris=True。"""
        dto = _make_dto_with_ephemeris()
        json_path, _ = save_artifact(dto, tmp_path)
        meta = json.loads(json_path.read_text(encoding="utf-8"))
        assert meta["has_ephemeris"] is True

    def test_save_artifact_no_ephemeris_flag(self, tmp_path):
        """无 ephemeris 时 has_ephemeris=False，NPZ 不含 eph_ 键。"""
        dto = OrbitDesignResultData(
            orbit_type="DRO",
            epoch_utc="2024-01-01T00:00:00",
            duration_day=365.25,
            initial_state=np.zeros(6),
            cr3bp_jacobi=3.0,
            states=_RNG.standard_normal((10, 6)),
            times=np.linspace(0, 1, 10),
            correction_converged=True,
            correction_iterations=3,
        )
        json_path, npz_path = save_artifact(dto, tmp_path)
        meta = json.loads(json_path.read_text(encoding="utf-8"))
        assert meta["has_ephemeris"] is False
        with np.load(npz_path) as data:
            assert not any(k.startswith("eph_") for k in data.files)


class TestSaveControlResult:
    def test_save_control_result_writes_ephemeris_dir(self, tmp_path):
        """save_control_result 写入 output/ephemeris/ 目录。"""
        result = _make_control_result()
        json_path, npz_path = save_control_result(result, tmp_path)
        assert json_path.parent.name == "ephemeris"
        assert json_path.exists()
        assert npz_path.exists()

    def test_save_control_result_filename_matches_discovery(self, tmp_path):
        """文件名 orbit_ephemeris_<ts> 与 discovery._EPHEMERIS_RE 兼容。"""
        result = _make_control_result()
        json_path, _ = save_control_result(result, tmp_path)
        assert re.match(r"^orbit_ephemeris_\d+\.json$", json_path.name), (
            f"文件名 {json_path.name} 与 _EPHEMERIS_RE 不兼容"
        )

    def test_save_control_result_json_metadata(self, tmp_path):
        """JSON 含 total_delta_v_mps / n_maneuvers / num_failed / mu。"""
        result = _make_control_result()
        json_path, _ = save_control_result(result, tmp_path)
        meta = json.loads(json_path.read_text(encoding="utf-8"))
        assert meta["artifact_type"] == "ephemeris"
        assert meta["source_tool"] == "control_orbit"
        assert meta["num_failed"] == 1
        assert meta["n_maneuvers"] == 2
        assert meta["total_delta_v_mps"] == pytest.approx(0.8)
        assert meta["mu"] == pytest.approx(0.012153645822478)
        assert meta["states_shape"] == [50, 6]

    def test_save_control_result_npz_arrays(self, tmp_path):
        """NPZ 含 controlled_states + controlled_times。"""
        result = _make_control_result()
        _, npz_path = save_control_result(result, tmp_path)
        with np.load(npz_path) as data:
            np.testing.assert_array_equal(data["states"], result.controlled_states)
            np.testing.assert_array_equal(data["times"], result.controlled_times)

    def test_save_control_result_no_npz_when_all_failed(self, tmp_path):
        """全失败（controlled_states=None）时仅写 JSON，不写 NPZ。"""
        result = ControlResultData(
            num_failed=5,
            sk_statistic_rows=np.empty((0, 3)),
            maneuvers_mjd_tdb=np.array([]),
            maneuvers_delta_v_mps=np.array([]),
            controlled_states=None,
            controlled_times=None,
            mu=None,
        )
        json_path, npz_path = save_control_result(result, tmp_path)
        assert json_path.exists()
        assert not npz_path.exists()
        meta = json.loads(json_path.read_text(encoding="utf-8"))
        assert meta["arrays_file"] is None
        assert meta["states_shape"] is None

    def test_save_control_result_discoverable(self, tmp_path):
        """save_control_result → discover_artifacts 互操作。"""
        result = _make_control_result()
        save_control_result(result, tmp_path)
        artifacts = discover_artifacts(tmp_path)
        assert len(artifacts) == 1
        a = artifacts[0]
        assert a.artifact_type == "ephemeris"


class TestLoadArtifactArraysEphemeris:
    def test_load_artifact_arrays_restores_ephemeris_to_extra(self, tmp_path):
        """存带 ephemeris 的 NPZ → load → extra["ephemeris"] 含 position_km 等。"""
        dto = _make_dto_with_ephemeris()
        json_path, _ = save_artifact(dto, tmp_path)
        artifacts = discover_artifacts(tmp_path)
        assert len(artifacts) == 1
        a = artifacts[0]
        assert "ephemeris" not in a.extra  # discovery 不加载 NPZ 内的 eph_
        assert load_artifact_arrays(a) is True
        eph = a.extra.get("ephemeris")
        assert eph is not None
        assert "position_km" in eph
        assert "synodic_position" in eph
        np.testing.assert_array_equal(eph["position_km"], dto.ephemeris["position_km"])

    def test_load_old_npz_without_ephemeris_no_crash(self, tmp_path):
        """旧 NPZ（仅 states/times）→ load → extra 无 "ephemeris"，不崩。"""
        dto = OrbitDesignResultData(
            orbit_type="DRO",
            epoch_utc="2024-01-01T00:00:00",
            duration_day=365.25,
            initial_state=np.zeros(6),
            cr3bp_jacobi=3.0,
            states=_RNG.standard_normal((10, 6)),
            times=np.linspace(0, 1, 10),
            correction_converged=True,
            correction_iterations=3,
        )
        save_artifact(dto, tmp_path)
        artifacts = discover_artifacts(tmp_path)
        assert len(artifacts) == 1
        a = artifacts[0]
        assert load_artifact_arrays(a) is True
        assert "ephemeris" not in a.extra
        # states/times 仍正常加载
        assert a.state_data is not None
        assert a.times is not None
