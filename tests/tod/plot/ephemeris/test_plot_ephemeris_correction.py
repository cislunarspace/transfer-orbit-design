# pyright: reportArgumentType=false
"""Tests for plot_ephemeris_correction helpers."""

import pytest

from tod.plot.ephemeris.plot_ephemeris_correction import (
    J2000_AXIS_LABELS,
    resolve_reference_epoch,
)


class TestResolveReferenceEpoch:
    def test_returns_json_epoch_when_no_request(self):
        eph_data = {"reference_epoch": "2025-06-21T11:00:06"}
        assert resolve_reference_epoch(eph_data, None) == "2025-06-21T11:00:06"

    def test_returns_json_epoch_when_request_matches(self):
        eph_data = {"reference_epoch": "2025-06-21T11:00:06"}
        assert resolve_reference_epoch(eph_data, "2025-06-21T11:00:06") == "2025-06-21T11:00:06"

    def test_raises_when_request_mismatches_json(self):
        eph_data = {"reference_epoch": "2025-06-21T11:00:06"}
        with pytest.raises(ValueError, match="不一致"):
            resolve_reference_epoch(eph_data, "2025-06-21T12:00:00")

    def test_raises_when_json_missing_reference_epoch(self):
        eph_data = {"converged": True}
        with pytest.raises(ValueError, match="缺少 reference_epoch"):
            resolve_reference_epoch(eph_data, None)

    def test_raises_when_json_missing_and_request_provided(self):
        eph_data = {"converged": True}
        with pytest.raises(ValueError, match="缺少 reference_epoch"):
            resolve_reference_epoch(eph_data, "2025-06-21T11:00:06")


class TestJ2000AxisLabels:
    def test_labels_are_du(self):
        assert J2000_AXIS_LABELS == ("X (DU)", "Y (DU)", "Z (DU)")

    def test_has_three_axes(self):
        assert len(J2000_AXIS_LABELS) == 3
