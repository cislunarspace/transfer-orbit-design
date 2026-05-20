"""Tests for the Halo ephemeris conversion script entrypoint.

The heavy SPICE/e2m2e workflow lives in tod.generates.ephemeris._conversion;
this module verifies that the Halo user-facing script stays a thin, explicit CLI
entrypoint.
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from tod.generates.ephemeris import _conversion
from tod.generates.ephemeris import correct_halo_to_ephemeris


def test_main_requires_input_file_and_reference_epoch():
    with pytest.raises(SystemExit):
        correct_halo_to_ephemeris.main([])

    with pytest.raises(SystemExit):
        correct_halo_to_ephemeris.main(["--input-file", "orbit.json"])

    with pytest.raises(SystemExit):
        correct_halo_to_ephemeris.main(
            ["--reference-epoch", "2025-06-21T11:00:06"]
        )


def test_main_delegates_to_shared_single_conversion():
    argv = [
        "--input-file",
        "orbit.json",
        "--reference-epoch",
        "2025-06-21T11:00:06",
    ]

    with patch.object(_conversion, "run_single_conversion", return_value={"ok": True}) as run:
        assert correct_halo_to_ephemeris.main(argv) == {"ok": True}

    config = run.call_args.args[0]
    assert config.orbit_type == "halo"
    assert config.input_file == Path("orbit.json")
    assert config.reference_epoch == "2025-06-21T11:00:06"
    assert config.method == "two_level"
    assert config.patch_points == 10
    assert config.position_tol == 1e-3
    assert config.velocity_tol == 1e-6
    assert config.bodies == ("EARTH", "MOON", "SUN")
    assert config.include_full_trajectory is True


def test_main_passes_explicit_options_to_shared_conversion(tmp_path):
    kernel_dir = tmp_path / "kernels"
    argv = [
        "--input-file",
        "family.json",
        "--reference-epoch",
        "2026-01-02T03:04:05",
        "--method",
        "standard",
        "--patch-points",
        "12",
        "--position-tol",
        "2e-3",
        "--velocity-tol",
        "3e-6",
        "--spice-kernel-dir",
        str(kernel_dir),
        "--bodies",
        "EARTH,MOON",
        "--orbit-index",
        "2",
        "--output-file",
        "result.json",
        "--per-orbit-workers",
        "4",
    ]

    with patch.object(_conversion, "run_single_conversion", return_value={"ok": True}) as run:
        correct_halo_to_ephemeris.main(argv)

    config = run.call_args.args[0]
    assert config.method == "standard"
    assert config.patch_points == 12
    assert config.position_tol == 2e-3
    assert config.velocity_tol == 3e-6
    assert config.spice_kernel_dir == kernel_dir
    assert config.bodies == ("EARTH", "MOON")
    assert config.orbit_index == 2
    assert config.output_file == Path("result.json")
    assert config.per_orbit_workers == 4
