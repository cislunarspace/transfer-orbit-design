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
    except Exception:
        pytest.skip("QApplication 不可用")


def _make_result_data() -> OrbitDesignResultData:
    n = 50
    return OrbitDesignResultData(
        orbit_type="DRO",
        epoch_utc="2024-01-01T00:00:00",
        duration_day=365.25,
        initial_state=np.zeros(6),
        cr3bp_jacobi=3.0058,
        states=np.random.randn(n, 6),
        times=np.linspace(0, 365.25, n),
        correction_converged=True,
        correction_iterations=3,
    )


class TestOnDesignFinishedPersistence:
    def test_calls_save_artifact_and_sets_output_path(self, qapp):
        from src.app.main_window import MainWindow

        window = MainWindow()
        result = _make_result_data()

        with patch("src.app.main_window.save_artifact") as mock_save:
            mock_save.return_value = Path("/fake/dro_001.json")
            window._on_design_finished(result)
            mock_save.assert_called_once_with(result, OUTPUT_DIR)

        # Artifact should have output_path set
        artifacts = window._project.artifacts
        assert len(artifacts) == 1
        assert artifacts[0].output_path == Path("/fake/dro_001.json")


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

        # Simulate click — should lazy-load
        window._on_artifact_clicked(a.artifact_id)
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
