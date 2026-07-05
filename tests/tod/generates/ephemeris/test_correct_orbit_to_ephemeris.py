"""Tests for the unified ephemeris conversion script (correct_orbit_to_ephemeris.py).

The heavy SPICE/e2m2e workflow lives in tod.generates.ephemeris._conversion;
this module verifies the unified user-facing CLI stays thin and delegates
appropriately while adding timing and geocentric-distance diagnostics.
"""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from tod.generates.ephemeris import _conversion
from tod.generates.ephemeris import correct_orbit_to_ephemeris


@pytest.fixture
def fake_deps():
    """Return a ConversionDependencies with fully mocked heavy deps."""
    orbit = SimpleNamespace(period=1.0, states=[[1, 2, 3, 4, 5, 6]])
    result = SimpleNamespace(
        converged=True,
        iterations=4,
        max_residual=1e-4,
        residual_history=[1e-2, 1e-4],
        velocity_residual=1e-7,
        velocity_residual_history=[1e-5, 1e-7],
        t_patch=[10.0, 20.0],
        state_patch=[[1.0, 0, 0, 0, 0, 0], [2.0, 0, 0, 0, 0, 0]],
    )
    dynamics = MagicMock()
    dynamics.propagate.return_value = {
        "states": [[1, 0, 0, 0, 0, 0], [2, 0, 0, 0, 0, 0]],
        "time": [10, 20],
    }
    return _conversion.ConversionDependencies(
        build_orbit=lambda payload: orbit,
        build_dynamics=lambda cfg: dynamics,
        reference_et=lambda cfg: 123.0,
        sample_patch_points=MagicMock(return_value=([0.0, 1.0], [[1], [2]])),
        convert_to_j2000=MagicMock(return_value=([10.0, 20.0], [[10], [20]])),
        correct_patch_points=MagicMock(return_value=result),
    )


def _make_minimal_input(tmp_path: Path) -> Path:
    """Create a minimal single-orbit JSON that satisfies the loader."""
    p = tmp_path / "orbit.json"
    p.write_text(
        json.dumps({"states": [[1, 2, 3, 4, 5, 6]], "times": [0], "period": 1.0}),
        encoding="utf-8",
    )
    return p


class TestArgParsing:
    """Validate the unified CLI argument surface."""

    def test_requires_input_file_and_reference_epoch(self):
        with pytest.raises(SystemExit):
            correct_orbit_to_ephemeris.main([])

        with pytest.raises(SystemExit):
            correct_orbit_to_ephemeris.main(["--input-file", "orbit.json"])

        with pytest.raises(SystemExit):
            correct_orbit_to_ephemeris.main(
                ["--reference-epoch", "2025-06-21T11:00:06"]
            )

    def test_defaults(self, tmp_path):
        args = correct_orbit_to_ephemeris.build_parser().parse_args(
            ["--input-file", "orbit.json", "--reference-epoch", "2025-06-21T11:00:06"]
        )
        assert args.orbit_type == "dro"
        assert args.method == "two_level"
        assert args.position_tol == 1e-3
        assert args.velocity_tol is None  # follows position_tol
        assert args.patch_points == 10
        assert args.max_iter == 50
        assert args.output_prefix.replace("\\", "/").endswith("output/ephemeris/orbit_ephemeris")
        assert args.orbit_index is None
        assert args.include_full_trajectory is True

    def test_explicit_options(self, tmp_path):
        kernel_dir = tmp_path / "kernels"
        args = correct_orbit_to_ephemeris.build_parser().parse_args(
            [
                "--input-file",
                "family.json",
                "--reference-epoch",
                "2026-01-02T03:04:05",
                "--orbit-type",
                "halo",
                "--method",
                "standard",
                "--patch-points",
                "12",
                "--position-tol",
                "2e-3",
                "--velocity-tol",
                "3e-6",
                "--max-iter",
                "30",
                "--spice-kernel-dir",
                str(kernel_dir),
                "--bodies",
                "EARTH,MOON",
                "--orbit-index",
                "2",
                "--output-prefix",
                "my_prefix",
                "--per-orbit-workers",
                "4",
            ]
        )
        assert args.orbit_type == "halo"
        assert args.method == "standard"
        assert args.patch_points == 12
        assert args.position_tol == 2e-3
        assert args.velocity_tol == 3e-6
        assert args.max_iter == 30
        assert args.spice_kernel_dir == str(kernel_dir)
        assert args.bodies == "EARTH,MOON"
        assert args.orbit_index == 2
        assert args.output_prefix == "my_prefix"
        assert args.per_orbit_workers == 4

    def test_velocity_tol_defaults_to_position_tol_when_not_specified(self, tmp_path):
        parser = correct_orbit_to_ephemeris.build_parser()
        args = parser.parse_args(
            [
                "--input-file",
                "orbit.json",
                "--reference-epoch",
                "2025-06-21T11:00:06",
                "--position-tol",
                "1e-6",
            ]
        )
        config = correct_orbit_to_ephemeris.config_from_args(args)
        assert config.velocity_tol == 1e-6

    def test_velocity_tol_preserved_when_explicit(self, tmp_path):
        parser = correct_orbit_to_ephemeris.build_parser()
        args = parser.parse_args(
            [
                "--input-file",
                "orbit.json",
                "--reference-epoch",
                "2025-06-21T11:00:06",
                "--position-tol",
                "1e-3",
                "--velocity-tol",
                "5e-7",
            ]
        )
        config = correct_orbit_to_ephemeris.config_from_args(args)
        assert config.velocity_tol == 5e-7

    def test_rejects_unknown_method(self):
        parser = correct_orbit_to_ephemeris.build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(
                [
                    "--input-file",
                    "orbit.json",
                    "--reference-epoch",
                    "2025-06-21T11:00:06",
                    "--method",
                    "bogus",
                ]
            )

    def test_rejects_unknown_orbit_type(self):
        parser = correct_orbit_to_ephemeris.build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(
                [
                    "--input-file",
                    "orbit.json",
                    "--reference-epoch",
                    "2025-06-21T11:00:06",
                    "--orbit-type",
                    "bogus",
                ]
            )


class TestScriptDelegation:
    """Confirm thin script delegates to _conversion.run_single_conversion."""

    def test_delegates_with_correct_orbit_type(self, fake_deps):
        argv = ["--input-file", "orbit.json", "--reference-epoch", "2025-06-21T11:00:06"]

        with patch.object(
            _conversion, "run_single_conversion", return_value={"ok": True}
        ) as run:
            correct_orbit_to_ephemeris.main(argv)

        config = run.call_args.args[0]
        assert config.orbit_type == "dro"
        assert config.method == "two_level"

    def test_delegates_with_halo_orbit_type(self, fake_deps):
        argv = [
            "--input-file",
            "orbit.json",
            "--reference-epoch",
            "2025-06-21T11:00:06",
            "--orbit-type",
            "halo",
        ]

        with patch.object(
            _conversion, "run_single_conversion", return_value={"ok": True}
        ) as run:
            correct_orbit_to_ephemeris.main(argv)

        config = run.call_args.args[0]
        assert config.orbit_type == "halo"

    def test_delegates_with_homotopy_method(self, fake_deps):
        argv = [
            "--input-file",
            "orbit.json",
            "--reference-epoch",
            "2025-06-21T11:00:06",
            "--method",
            "homotopy",
        ]

        with patch.object(
            _conversion, "run_single_conversion", return_value={"ok": True}
        ) as run:
            correct_orbit_to_ephemeris.main(argv)

        config = run.call_args.args[0]
        assert config.method == "homotopy"


class TestOutputFileNaming:
    """Validate {prefix}_{method}_tol{tol}.json naming."""

    def test_generates_expected_filename(self, tmp_path, fake_deps):
        input_file = _make_minimal_input(tmp_path)
        output_prefix = str(tmp_path / "result")
        argv = [
            "--input-file",
            str(input_file),
            "--reference-epoch",
            "2025-06-21T11:00:06",
            "--method",
            "two_level",
            "--position-tol",
            "1e-3",
            "--output-prefix",
            output_prefix,
        ]

        with patch.object(_conversion, "run_single_conversion") as run:
            run.return_value = {
                "metadata": {},
                "result": {
                    "status": "success",
                    "converged": True,
                    "full_trajectory_states": [[1, 0, 0, 0, 0, 0]],
                },
            }
            correct_orbit_to_ephemeris.main(argv)

        expected = tmp_path / "result_two_level_tol1e-3.json"
        assert expected.exists()

    def test_generates_filename_with_standard_method(self, tmp_path, fake_deps):
        input_file = _make_minimal_input(tmp_path)
        output_prefix = str(tmp_path / "myrun")
        argv = [
            "--input-file",
            str(input_file),
            "--reference-epoch",
            "2025-06-21T11:00:06",
            "--method",
            "standard",
            "--position-tol",
            "1e-6",
            "--output-prefix",
            output_prefix,
        ]

        with patch.object(_conversion, "run_single_conversion") as run:
            run.return_value = {
                "metadata": {},
                "result": {
                    "status": "success",
                    "converged": True,
                    "full_trajectory_states": [[1, 0, 0, 0, 0, 0]],
                },
            }
            correct_orbit_to_ephemeris.main(argv)

        expected = tmp_path / "myrun_standard_tol1e-6.json"
        assert expected.exists()


class TestDiagnostics:
    """Validate timing and geocentric distance computation."""

    def test_result_contains_timing_fields(self, tmp_path, fake_deps):
        input_file = _make_minimal_input(tmp_path)
        output_prefix = str(tmp_path / "out")
        argv = [
            "--input-file",
            str(input_file),
            "--reference-epoch",
            "2025-06-21T11:00:06",
            "--output-prefix",
            output_prefix,
        ]

        with patch.object(_conversion, "run_single_conversion") as run:
            run.return_value = {
                "metadata": {},
                "result": {
                    "status": "success",
                    "converged": True,
                    "full_trajectory_states": [[1, 0, 0, 0, 0, 0], [2, 0, 0, 0, 0, 0]],
                },
            }
            correct_orbit_to_ephemeris.main(argv)

        output_file = tmp_path / "out_two_level_tol1e-3.json"
        saved = json.loads(output_file.read_text(encoding="utf-8"))
        assert "timing_seconds" in saved
        assert isinstance(saved["timing_seconds"], float)
        assert saved["timing_seconds"] >= 0.0

    def test_result_contains_geocentric_distance(self, tmp_path, fake_deps):
        input_file = _make_minimal_input(tmp_path)
        output_prefix = str(tmp_path / "out")
        argv = [
            "--input-file",
            str(input_file),
            "--reference-epoch",
            "2025-06-21T11:00:06",
            "--output-prefix",
            output_prefix,
        ]

        with patch.object(_conversion, "run_single_conversion") as run:
            run.return_value = {
                "metadata": {},
                "result": {
                    "status": "success",
                    "converged": True,
                    "full_trajectory_states": [
                        [3, 4, 0, 0, 0, 0],  # dist = 5
                        [6, 8, 0, 0, 0, 0],  # dist = 10
                    ],
                },
            }
            correct_orbit_to_ephemeris.main(argv)

        output_file = tmp_path / "out_two_level_tol1e-3.json"
        saved = json.loads(output_file.read_text(encoding="utf-8"))
        assert saved["geocentric_distance_mean_km"] == 7.5
        assert saved["geocentric_distance_std_km"] == 2.5

    def test_geocentric_distance_skipped_when_no_full_trajectory(self, tmp_path, fake_deps):
        input_file = _make_minimal_input(tmp_path)
        output_prefix = str(tmp_path / "out")
        argv = [
            "--input-file",
            str(input_file),
            "--reference-epoch",
            "2025-06-21T11:00:06",
            "--output-prefix",
            output_prefix,
            "--no-include-full-trajectory",
        ]

        with patch.object(_conversion, "run_single_conversion") as run:
            run.return_value = {
                "metadata": {},
                "result": {
                    "status": "success",
                    "converged": True,
                },
            }
            correct_orbit_to_ephemeris.main(argv)

        output_file = tmp_path / "out_two_level_tol1e-3.json"
        saved = json.loads(output_file.read_text(encoding="utf-8"))
        assert "geocentric_distance_mean_km" not in saved

    def test_status_field_success(self, tmp_path, fake_deps):
        input_file = _make_minimal_input(tmp_path)
        output_prefix = str(tmp_path / "out")
        argv = [
            "--input-file",
            str(input_file),
            "--reference-epoch",
            "2025-06-21T11:00:06",
            "--output-prefix",
            output_prefix,
        ]

        with patch.object(_conversion, "run_single_conversion") as run:
            run.return_value = {
                "metadata": {},
                "result": {"status": "success", "converged": True},
            }
            correct_orbit_to_ephemeris.main(argv)

        output_file = tmp_path / "out_two_level_tol1e-3.json"
        saved = json.loads(output_file.read_text(encoding="utf-8"))
        assert saved["status"] == "success"

    def test_status_field_not_converged(self, tmp_path, fake_deps):
        input_file = _make_minimal_input(tmp_path)
        output_prefix = str(tmp_path / "out")
        argv = [
            "--input-file",
            str(input_file),
            "--reference-epoch",
            "2025-06-21T11:00:06",
            "--output-prefix",
            output_prefix,
        ]

        with patch.object(_conversion, "run_single_conversion") as run:
            run.return_value = {
                "metadata": {},
                "result": {"status": "not_converged", "converged": False},
            }
            correct_orbit_to_ephemeris.main(argv)

        output_file = tmp_path / "out_two_level_tol1e-3.json"
        saved = json.loads(output_file.read_text(encoding="utf-8"))
        assert saved["status"] == "not_converged"

    def test_failure_handled_with_error_field(self, tmp_path, fake_deps):
        input_file = _make_minimal_input(tmp_path)
        output_prefix = str(tmp_path / "out")
        argv = [
            "--input-file",
            str(input_file),
            "--reference-epoch",
            "2025-06-21T11:00:06",
            "--output-prefix",
            output_prefix,
        ]

        with patch.object(_conversion, "run_single_conversion") as run:
            run.side_effect = RuntimeError("SPICE failure")
            correct_orbit_to_ephemeris.main(argv)

        output_file = tmp_path / "out_two_level_tol1e-3.json"
        saved = json.loads(output_file.read_text(encoding="utf-8"))
        assert saved["status"] == "failure"
        assert "SPICE failure" in saved["error"]
