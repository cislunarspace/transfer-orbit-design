"""tests for main_window persistence integration (issue #338)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from src.commons.paths import OUTPUT_DIR
from src.engine.facade_bridge import OrbitDesignResultData
from src.engine.persistence import save_artifact
from src.model.discovery import discover_artifacts


@pytest.fixture()
def qapp():
    try:
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        return app
    except ImportError:
        pytest.skip("QApplication 不可用")


_RNG = np.random.default_rng(seed=42)


def _make_result_data() -> OrbitDesignResultData:
    n = 50
    return OrbitDesignResultData(
        orbit_type="DRO",
        epoch_utc="2024-01-01T00:00:00",
        duration_day=365.25,
        initial_state=np.zeros(6),
        cr3bp_jacobi=3.0058,
        states=_RNG.standard_normal((n, 6)),
        times=np.linspace(0, 365.25, n),
        correction_converged=True,
        correction_iterations=3,
    )


class TestOnDesignFinishedPersistence:
    def test_calls_save_artifact_and_sets_output_path(self, qapp):
        from src.app.main_window import MainWindow

        with patch("src.app.main_window.discover_artifacts", return_value=[]):
            window = MainWindow()
        result = _make_result_data()

        # S2: save_artifact 现在返回 (json_path, npz_path) 元组
        with patch("src.app.main_window.save_artifact") as mock_save:
            mock_save.return_value = (Path("/fake/dro_001.json"), Path("/fake/dro_001.npz"))
            window._on_design_finished(result)
            mock_save.assert_called_once_with(result, OUTPUT_DIR)

        # Artifact should have output_path set
        artifacts = window._project.artifacts
        assert len(artifacts) == 1
        assert artifacts[0].output_path == Path("/fake/dro_001.json")
        # 元数据键应与磁盘 JSON 一致 (Spec S1)
        assert artifacts[0].extra["arrays_file"] == "dro_001.npz"
        assert artifacts[0].extra["cr3bp_jacobi"] == pytest.approx(3.0058)
        assert artifacts[0].extra["epoch_utc"] == "2024-01-01T00:00:00"
        assert artifacts[0].extra["correction_converged"] is True
        assert artifacts[0].extra["correction_iterations"] == 3

    def test_save_failure_keeps_artifact_in_memory(self, qapp):
        """S4: 持久化失败时 in-memory Artifact 仍可用，状态栏明确显示。"""
        from src.app.main_window import MainWindow

        with patch("src.app.main_window.discover_artifacts", return_value=[]):
            window = MainWindow()
        result = _make_result_data()

        with patch("src.app.main_window.save_artifact") as mock_save:
            mock_save.side_effect = OSError("disk full")
            window._on_design_finished(result)

        # 即使落盘失败，Artifact 仍然存在且 state_data 可用
        artifacts = window._project.artifacts
        assert len(artifacts) == 1
        assert artifacts[0].output_path is None
        assert artifacts[0].state_data is not None
        assert artifacts[0].extra["arrays_file"] == ""
        # 状态栏显示明确错误（S4：覆盖"设计完成"以保留错误可见性）
        assert window._status_bar.currentMessage() == "设计完成但持久化失败"


class TestLazyLoadArrays:
    def test_loads_npz_on_click(self, qapp, tmp_path):
        from src.app.main_window import MainWindow

        # Save a real artifact to disk
        result = _make_result_data()
        save_artifact(result, tmp_path)

        # Discover it (no arrays loaded)
        artifacts = discover_artifacts(tmp_path)
        assert len(artifacts) == 1
        a = artifacts[0]
        assert a.state_data is None

        # Add to window's project
        window = MainWindow()
        window._project.add(a)

        # AC #4: verify plot_orbit 被调用 (Spec S5)
        with patch.object(window._viz, "plot_orbit") as mock_plot:
            window._on_artifact_clicked(a.artifact_id)
            mock_plot.assert_called_once()

        assert a.state_data is not None
        assert a.state_data.shape == (50, 6)
        assert a.times is not None
        assert a.times.shape == (50,)


class TestDiscoveryOnInit:
    def test_recovers_existing_artifacts(self, qapp, tmp_path, monkeypatch):
        """MainWindow init should discover artifacts from OUTPUT_DIR."""
        # Create a fake artifact on disk
        result = _make_result_data()
        save_artifact(result, tmp_path)

        # Patch OUTPUT_DIR to point to tmp_path
        monkeypatch.setattr("src.app.main_window.OUTPUT_DIR", tmp_path)

        from src.app.main_window import MainWindow

        window = MainWindow()
        assert len(window._project.artifacts) >= 1
