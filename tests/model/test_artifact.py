from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from src.model.artifact import Artifact


class TestArtifactDefaults:
    """Verify that Artifact fields have sensible defaults."""

    def test_id_is_8_hex_chars(self) -> None:
        art = Artifact()
        assert len(art.artifact_id) == 8
        # All characters must be hex digits
        assert all(c in "0123456789abcdef" for c in art.artifact_id)

    def test_unique_ids(self) -> None:
        ids = {Artifact().artifact_id for _ in range(50)}
        # With 50 random 8-char hex ids collisions are astronomically unlikely
        assert len(ids) == 50

    def test_created_at_is_utc(self) -> None:
        art = Artifact()
        assert art.created_at.tzinfo == UTC

    def test_arrays_default_to_none(self) -> None:
        art = Artifact()
        assert art.state_data is None
        assert art.times is None

    def test_extra_defaults_to_empty_dict(self) -> None:
        art = Artifact()
        assert art.extra == {}

    def test_output_path_defaults_to_none(self) -> None:
        art = Artifact()
        assert art.output_path is None


class TestToSummary:
    """to_summary() should exclude large array fields."""

    def test_no_state_data_key(self) -> None:
        art = Artifact(state_data=np.zeros((10, 6)))
        summary = art.to_summary()
        assert "state_data" not in summary

    def test_no_times_key(self) -> None:
        art = Artifact(times=np.linspace(0, 1, 10))
        summary = art.to_summary()
        assert "times" not in summary

    def test_contains_basic_fields(self) -> None:
        art = Artifact(
            artifact_type="orbit",
            label="test orbit",
            orbit_type="DRO",
        )
        summary = art.to_summary()
        assert summary["artifact_type"] == "orbit"
        assert summary["label"] == "test orbit"
        assert summary["orbit_type"] == "DRO"

    def test_output_path_serialised_as_str(self) -> None:
        p = Path("/tmp/out.json")
        art = Artifact(output_path=p)
        summary = art.to_summary()
        assert summary["output_path"] == str(p)

    def test_created_at_is_isoformat(self) -> None:
        art = Artifact()
        summary = art.to_summary()
        # Should be parseable back as ISO format
        datetime.fromisoformat(summary["created_at"])
