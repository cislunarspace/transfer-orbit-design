from __future__ import annotations

import json
from pathlib import Path

from src.model.discovery import discover_artifacts


class TestDiscoverArtifacts:
    """Test discover_artifacts against a mock output directory."""

    def test_classifies_dro_orbit(self, tmp_path: Path) -> None:
        dro_dir = tmp_path / "dro"
        dro_dir.mkdir()
        (dro_dir / "dro_001.json").write_text(
            json.dumps({"orbit_type": "DRO"}), encoding="utf-8"
        )
        arts = discover_artifacts(tmp_path)
        assert len(arts) == 1
        assert arts[0].artifact_type == "orbit"
        assert arts[0].orbit_type == "DRO"
        assert arts[0].output_path == dro_dir / "dro_001.json"

    def test_classifies_dro_family(self, tmp_path: Path) -> None:
        dro_dir = tmp_path / "dro"
        dro_dir.mkdir()
        (dro_dir / "dro_001_family_set1.json").write_text(
            json.dumps({"orbit_type": "DRO"}), encoding="utf-8"
        )
        arts = discover_artifacts(tmp_path)
        assert len(arts) == 1
        assert arts[0].artifact_type == "family"

    def test_classifies_halo_orbit(self, tmp_path: Path) -> None:
        halo_dir = tmp_path / "halo"
        halo_dir.mkdir()
        (halo_dir / "halo_north_L1.json").write_text(
            json.dumps({"orbit_type": "Halo"}), encoding="utf-8"
        )
        arts = discover_artifacts(tmp_path)
        assert len(arts) == 1
        assert arts[0].artifact_type == "orbit"
        assert arts[0].orbit_type == "Halo"

    def test_classifies_ephemeris(self, tmp_path: Path) -> None:
        eph_dir = tmp_path / "ephemeris"
        eph_dir.mkdir()
        (eph_dir / "orbit_ephemeris_dro.json").write_text(
            json.dumps({"orbit_type": "DRO"}), encoding="utf-8"
        )
        arts = discover_artifacts(tmp_path)
        assert len(arts) == 1
        assert arts[0].artifact_type == "ephemeris"

    def test_classifies_corrected_transfer(self, tmp_path: Path) -> None:
        tr_dir = tmp_path / "transfer"
        tr_dir.mkdir()
        (tr_dir / "corrected_transfer_001.json").write_text(
            json.dumps({}), encoding="utf-8"
        )
        arts = discover_artifacts(tmp_path)
        assert len(arts) == 1
        assert arts[0].artifact_type == "transfer"

    def test_classifies_optimization_transfer(self, tmp_path: Path) -> None:
        tr_dir = tmp_path / "transfer"
        tr_dir.mkdir()
        (tr_dir / "optimization_run1.json").write_text(
            json.dumps({}), encoding="utf-8"
        )
        arts = discover_artifacts(tmp_path)
        assert len(arts) == 1
        assert arts[0].artifact_type == "transfer"

    def test_nonexistent_dir_returns_empty(self, tmp_path: Path) -> None:
        assert discover_artifacts(tmp_path / "nonexistent") == []

    def test_unrecognised_files_skipped(self, tmp_path: Path) -> None:
        dro_dir = tmp_path / "dro"
        dro_dir.mkdir()
        (dro_dir / "readme.txt").write_text("ignore me", encoding="utf-8")
        (dro_dir / "dro_001.json").write_text(
            json.dumps({"orbit_type": "DRO"}), encoding="utf-8"
        )
        arts = discover_artifacts(tmp_path)
        assert len(arts) == 1
        assert arts[0].artifact_type == "orbit"

    def test_unrecognised_json_in_subdir_skipped(self, tmp_path: Path) -> None:
        """JSON files that don't match naming patterns are skipped."""
        dro_dir = tmp_path / "dro"
        dro_dir.mkdir()
        (dro_dir / "some_other.json").write_text(
            json.dumps({"orbit_type": "DRO"}), encoding="utf-8"
        )
        arts = discover_artifacts(tmp_path)
        assert arts == []

    def test_broken_json_skipped(self, tmp_path: Path) -> None:
        dro_dir = tmp_path / "dro"
        dro_dir.mkdir()
        (dro_dir / "dro_001.json").write_text("NOT VALID JSON {{{", encoding="utf-8")
        (dro_dir / "dro_002.json").write_text(
            json.dumps({"orbit_type": "DRO"}), encoding="utf-8"
        )
        arts = discover_artifacts(tmp_path)
        assert len(arts) == 1
        assert arts[0].label == "dro_002"

    def test_source_tool_is_empty(self, tmp_path: Path) -> None:
        dro_dir = tmp_path / "dro"
        dro_dir.mkdir()
        (dro_dir / "dro_001.json").write_text(
            json.dumps({"orbit_type": "DRO"}), encoding="utf-8"
        )
        arts = discover_artifacts(tmp_path)
        assert arts[0].source_tool == ""

    def test_created_at_from_mtime(self, tmp_path: Path) -> None:
        dro_dir = tmp_path / "dro"
        dro_dir.mkdir()
        p = dro_dir / "dro_001.json"
        p.write_text(json.dumps({"orbit_type": "DRO"}), encoding="utf-8")
        arts = discover_artifacts(tmp_path)
        # created_at should be close to now (within 60 seconds)
        import time
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        assert abs((now - arts[0].created_at).total_seconds()) < 60

    def test_state_data_and_times_loaded(self, tmp_path: Path) -> None:
        """When JSON contains 'states' and 'times', they are parsed into numpy arrays."""
        import numpy as np

        dro_dir = tmp_path / "dro"
        dro_dir.mkdir()
        payload = {
            "orbit_type": "DRO",
            "states": [[1.0, 2.0, 3.0, 4.0, 5.0, 6.0]] * 3,
            "times": [0.0, 0.5, 1.0],
        }
        (dro_dir / "dro_001.json").write_text(
            json.dumps(payload), encoding="utf-8"
        )
        arts = discover_artifacts(tmp_path)
        assert len(arts) == 1
        art = arts[0]
        assert art.state_data is not None
        assert art.times is not None
        assert art.state_data.shape == (3, 6)
        assert art.times.shape == (3,)
        np.testing.assert_allclose(art.state_data[0], [1, 2, 3, 4, 5, 6])
        np.testing.assert_allclose(art.times, [0.0, 0.5, 1.0])

    def test_missing_states_leaves_state_data_none(self, tmp_path: Path) -> None:
        """JSON without 'states' key results in state_data=None."""
        dro_dir = tmp_path / "dro"
        dro_dir.mkdir()
        (dro_dir / "dro_001.json").write_text(
            json.dumps({"orbit_type": "DRO"}), encoding="utf-8"
        )
        arts = discover_artifacts(tmp_path)
        assert arts[0].state_data is None
        assert arts[0].times is None
