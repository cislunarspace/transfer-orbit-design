# pyright: reportArgumentType=false, reportOptionalMemberAccess=false, reportAttributeAccessIssue=false, reportGeneralTypeIssues=false, reportCallIssue=false, reportFunctionMemberAccess=false
import importlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from tod.generates.ephemeris import _conversion


def _fake_adapter(finalize=None):
    orbit = SimpleNamespace(period=1.0, states=[[1, 2, 3, 4, 5, 6]])
    result = SimpleNamespace(
        converged=True,
        iterations=1,
        max_residual=1e-4,
        residual_history=[1e-4],
        velocity_residual=None,
        velocity_residual_history=None,
        t_patch=[10.0, 20.0],
        state_patch=[[1.0, 0, 0, 0, 0, 0], [2.0, 0, 0, 0, 0, 0]],
    )
    dynamics = MagicMock()
    dynamics.propagate.return_value = {
        "states": [[1, 0, 0, 0, 0, 0], [2, 0, 0, 0, 0, 0]],
        "time": [10, 20],
    }
    adapter = MagicMock(spec=_conversion.EphemerisConversionAdapter)
    adapter.build_orbit.return_value = orbit
    adapter.build_dynamics.return_value = dynamics
    adapter.reference_et.return_value = 123.0
    adapter.sample_patch_points.return_value = ([0.0, 1.0], [[1], [2]])
    adapter.convert_states.return_value = ([10.0, 20.0], [[10], [20]])
    adapter.correct.return_value = result
    if finalize is not None:
        adapter.finalize = finalize
    return adapter


def test_single_parser_requires_input_file_and_reference_epoch():
    parser = _conversion.build_single_parser("dro")

    with pytest.raises(SystemExit):
        parser.parse_args([])

    with pytest.raises(SystemExit):
        parser.parse_args(["--input-file", "orbit.json"])

    with pytest.raises(SystemExit):
        parser.parse_args(["--reference-epoch", "2025-06-21T11:00:06"])


def test_single_parser_defaults_to_reproducible_conversion_settings():
    parser = _conversion.build_single_parser("halo")

    args = parser.parse_args(
        [
            "--input-file",
            "orbit.json",
            "--reference-epoch",
            "2025-06-21T11:00:06",
        ]
    )
    config = _conversion.single_config_from_args(args, "halo")

    assert config.input_file == Path("orbit.json")
    assert config.reference_epoch == "2025-06-21T11:00:06"
    assert config.orbit_type == "halo"
    assert config.method == "two_level"
    assert config.patch_points == 10
    assert config.position_tol == 1e-3
    assert config.velocity_tol == 1e-6
    assert config.bodies == ("EARTH", "MOON", "SUN")
    assert config.orbit_index is None
    assert config.include_full_trajectory is True


def test_single_parser_accepts_explicit_conversion_settings(tmp_path):
    kernel_dir = tmp_path / "kernels"
    parser = _conversion.build_single_parser("dro")

    args = parser.parse_args(
        [
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
    )
    config = _conversion.single_config_from_args(args, "dro")

    assert config.method == "standard"
    assert config.patch_points == 12
    assert config.position_tol == 2e-3
    assert config.velocity_tol == 3e-6
    assert config.spice_kernel_dir == kernel_dir
    assert config.bodies == ("EARTH", "MOON")
    assert config.orbit_index == 2
    assert config.output_file == Path("result.json")
    assert config.per_orbit_workers == 4


def test_single_parser_rejects_unknown_method():
    parser = _conversion.build_single_parser("dro")

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


def test_single_parser_accepts_homotopy_method():
    parser = _conversion.build_single_parser("dro")

    args = parser.parse_args(
        [
            "--input-file",
            "orbit.json",
            "--reference-epoch",
            "2025-06-21T11:00:06",
            "--method",
            "homotopy",
        ]
    )
    config = _conversion.single_config_from_args(args, "dro")

    assert config.method == "homotopy"


def test_family_parser_defaults_to_serial_lightweight_continue_on_failure():
    parser = _conversion.build_family_parser("dro")

    args = parser.parse_args(
        [
            "--input-file",
            "family.json",
            "--reference-epoch",
            "2025-06-21T11:00:06",
        ]
    )
    config = _conversion.family_config_from_args(args, "dro")

    assert config.input_file == Path("family.json")
    assert config.orbit_type == "dro"
    assert config.method == "two_level"
    assert config.patch_points == 10
    assert config.family_workers == 1
    assert config.per_orbit_workers == 1
    assert config.fail_fast is False
    assert config.include_full_trajectory is False


def test_family_parser_accepts_fail_fast_parallelism_and_full_trajectory():
    parser = _conversion.build_family_parser("halo")

    args = parser.parse_args(
        [
            "--input-file",
            "family.json",
            "--reference-epoch",
            "2025-06-21T11:00:06",
            "--family-workers",
            "3",
            "--per-orbit-workers",
            "2",
            "--fail-fast",
            "--include-full-trajectory",
        ]
    )
    config = _conversion.family_config_from_args(args, "halo")

    assert config.family_workers == 3
    assert config.per_orbit_workers == 2
    assert config.fail_fast is True
    assert config.include_full_trajectory is True


def test_parser_rejects_non_positive_worker_counts():
    parser = _conversion.build_family_parser("halo")

    with pytest.raises(SystemExit):
        parser.parse_args(
            [
                "--input-file",
                "family.json",
                "--reference-epoch",
                "2025-06-21T11:00:06",
                "--family-workers",
                "0",
            ]
        )

    with pytest.raises(SystemExit):
        parser.parse_args(
            [
                "--input-file",
                "family.json",
                "--reference-epoch",
                "2025-06-21T11:00:06",
                "--per-orbit-workers",
                "0",
            ]
        )


def test_spice_kernel_dir_default_honors_environment(monkeypatch, tmp_path):
    kernel_dir = tmp_path / "kernels"
    monkeypatch.setenv("SPICE_KERNEL_DIR", str(kernel_dir))
    reloaded = importlib.reload(_conversion)

    try:
        parser = reloaded.build_single_parser("dro")
        args = parser.parse_args(
            [
                "--input-file",
                "orbit.json",
                "--reference-epoch",
                "2025-06-21T11:00:06",
            ]
        )
        config = reloaded.single_config_from_args(args, "dro")

        assert config.spice_kernel_dir == kernel_dir
    finally:
        importlib.reload(_conversion)


def test_load_single_orbit_accepts_single_orbit_json(tmp_path):
    input_file = tmp_path / "orbit.json"
    orbit_data = {"states": [[1, 2, 3, 4, 5, 6]], "times": [0], "period": 1.5}
    input_file.write_text(json.dumps(orbit_data), encoding="utf-8")

    loaded = _conversion.load_single_orbit_payload(input_file, orbit_index=None)

    assert loaded.orbit_index is None
    assert loaded.payload == orbit_data


def test_load_single_orbit_rejects_family_without_orbit_index(tmp_path):
    input_file = tmp_path / "family.json"
    input_file.write_text(json.dumps({"orbits": [{"period": 1.0}]}), encoding="utf-8")

    with pytest.raises(ValueError, match="--orbit-index"):
        _conversion.load_single_orbit_payload(input_file, orbit_index=None)


def test_load_single_orbit_selects_family_member_by_orbit_index(tmp_path):
    input_file = tmp_path / "family.json"
    input_file.write_text(
        json.dumps({"orbits": [{"period": 1.0}, {"period": 2.0}]}), encoding="utf-8"
    )

    loaded = _conversion.load_single_orbit_payload(input_file, orbit_index=1)

    assert loaded.orbit_index == 1
    assert loaded.payload == {"period": 2.0}


def test_load_single_orbit_rejects_out_of_range_orbit_index(tmp_path):
    input_file = tmp_path / "family.json"
    input_file.write_text(json.dumps({"orbits": [{"period": 1.0}]}), encoding="utf-8")

    with pytest.raises(IndexError, match="orbit index"):
        _conversion.load_single_orbit_payload(input_file, orbit_index=2)


def test_load_family_payloads_requires_family_json(tmp_path):
    input_file = tmp_path / "orbit.json"
    input_file.write_text(json.dumps({"states": [], "times": [], "period": 1.0}), encoding="utf-8")

    with pytest.raises(ValueError, match="orbits"):
        _conversion.load_family_payloads(input_file)


def test_load_family_payloads_returns_ordered_orbits(tmp_path):
    input_file = tmp_path / "family.json"
    input_file.write_text(
        json.dumps({"orbits": [{"period": 1.0}, {"period": 2.0}]}), encoding="utf-8"
    )

    loaded = _conversion.load_family_payloads(input_file)

    assert loaded == [{"period": 1.0}, {"period": 2.0}]


def test_run_family_payload_conversion_uses_requested_worker_count(monkeypatch):
    def serial_path(*args, **kwargs):
        raise AssertionError("family_workers > 1 should not use serial path")

    def convert(payload, index, include_full_trajectory):
        return {"period": payload["period"], "index": index}

    monkeypatch.setattr(_conversion, "_run_family_payload_conversion_serial", serial_path)

    result = _conversion.run_family_payload_conversion(
        [{"period": 1.0}, {"period": 2.0}],
        convert,
        fail_fast=False,
        include_full_trajectory=False,
        family_workers=2,
    )

    assert [entry["result"]["index"] for entry in result] == [0, 1]


def test_run_family_payload_conversion_records_parallel_failures_in_input_order():
    def convert(payload, index, include_full_trajectory):
        if index == 1:
            raise RuntimeError("bad orbit")
        return {"period": payload["period"], "index": index}

    result = _conversion.run_family_payload_conversion(
        [{"period": 1.0}, {"period": 2.0}, {"period": 3.0}],
        convert,
        fail_fast=False,
        include_full_trajectory=False,
        family_workers=2,
    )

    assert [entry["orbit_index"] for entry in result] == [0, 1, 2]
    assert [entry["status"] for entry in result] == ["success", "failure", "success"]
    assert result[1]["error"] == "bad orbit"


def test_run_family_payload_conversion_records_failures_and_continues():
    def convert(payload, index, include_full_trajectory):
        if index == 1:
            raise RuntimeError("bad orbit")
        return {"period": payload["period"], "full": include_full_trajectory}

    result = _conversion.run_family_payload_conversion(
        [{"period": 1.0}, {"period": 2.0}, {"period": 3.0}],
        convert,
        fail_fast=False,
        include_full_trajectory=False,
    )

    assert [entry["status"] for entry in result] == ["success", "failure", "success"]
    assert result[1]["orbit_index"] == 1
    assert result[1]["error"] == "bad orbit"
    assert result[2]["result"] == {"period": 3.0, "full": False}


def test_run_family_payload_conversion_fail_fast_stops_on_first_failure():
    def convert(payload, index, include_full_trajectory):
        if index == 1:
            raise RuntimeError("bad orbit")
        return {"period": payload["period"]}

    result = _conversion.run_family_payload_conversion(
        [{"period": 1.0}, {"period": 2.0}, {"period": 3.0}],
        convert,
        fail_fast=True,
        include_full_trajectory=True,
    )

    assert [entry["status"] for entry in result] == ["success", "failure"]


def test_unified_entry_script_delegates_to_single_conversion():
    from tod.generates.ephemeris import correct_orbit_to_ephemeris

    argv = ["--input-file", "orbit.json", "--reference-epoch", "2025-06-21T11:00:06"]

    with patch.object(
        _conversion, "run_single_conversion", return_value={"ok": "dro", "result": {"status": "success"}}
    ) as run:
        result = correct_orbit_to_ephemeris.main(argv)
        assert result["ok"] == "dro"
        assert "timing_seconds" in result
        assert run.call_args.args[0].orbit_type == "dro"

    argv_halo = [
        "--input-file", "orbit.json",
        "--reference-epoch", "2025-06-21T11:00:06",
        "--orbit-type", "halo",
    ]
    with patch.object(
        _conversion, "run_single_conversion", return_value={"ok": "halo", "result": {"status": "success"}}
    ) as run:
        result = correct_orbit_to_ephemeris.main(argv_halo)
        assert result["ok"] == "halo"
        assert "timing_seconds" in result
        assert run.call_args.args[0].orbit_type == "halo"


def test_family_entry_scripts_delegate_to_family_conversion():
    from tod.generates.ephemeris.family_correction import SCRIPT_ENTRIES

    assert len(SCRIPT_ENTRIES) == 2
    assert SCRIPT_ENTRIES[0].name == "correct_dro_family_to_ephemeris"
    assert SCRIPT_ENTRIES[1].name == "correct_halo_family_to_ephemeris"


def test_run_single_conversion_writes_output_file(tmp_path):
    input_file = tmp_path / "orbit.json"
    output_file = tmp_path / "single-result.json"
    input_file.write_text(
        json.dumps({"states": [[1, 2, 3, 4, 5, 6]], "times": [0], "period": 1.5}),
        encoding="utf-8",
    )
    config = _conversion.SingleConversionConfig(
        orbit_type="dro",
        input_file=input_file,
        reference_epoch="2025-06-21T11:00:06",
        method="two_level",
        patch_points=10,
        position_tol=1e-3,
        velocity_tol=1e-6,
        spice_kernel_dir=tmp_path / "kernels",
        bodies=("EARTH", "MOON", "SUN"),
        output_file=output_file,
        per_orbit_workers=1,
        orbit_index=None,
    )

    result = _conversion.run_single_conversion(config, adapter=_fake_adapter())
    saved = json.loads(output_file.read_text(encoding="utf-8"))

    assert result == saved
    assert saved["metadata"]["mode"] == "single"
    assert saved["metadata"]["orbit_type"] == "dro"
    assert saved["metadata"]["include_full_trajectory"] is True


def test_run_family_conversion_writes_lightweight_output_by_default(tmp_path):
    input_file = tmp_path / "family.json"
    output_file = tmp_path / "family-result.json"
    input_file.write_text(
        json.dumps({"orbits": [{"period": 1.0}, {"period": 2.0}]}),
        encoding="utf-8",
    )
    config = _conversion.FamilyConversionConfig(
        orbit_type="halo",
        input_file=input_file,
        reference_epoch="2025-06-21T11:00:06",
        method="two_level",
        patch_points=10,
        position_tol=1e-3,
        velocity_tol=1e-6,
        spice_kernel_dir=tmp_path / "kernels",
        bodies=("EARTH", "MOON", "SUN"),
        output_file=output_file,
        per_orbit_workers=1,
        family_workers=1,
        fail_fast=False,
        include_full_trajectory=False,
    )

    result = _conversion.run_family_conversion(config, adapter=_fake_adapter())
    saved = json.loads(output_file.read_text(encoding="utf-8"))

    assert result == saved
    assert saved["metadata"]["mode"] == "family"
    assert saved["metadata"]["orbit_type"] == "halo"
    assert saved["metadata"]["include_full_trajectory"] is False
    assert [entry["status"] for entry in saved["results"]] == ["success", "success"]


def test_run_family_conversion_uses_process_workers_for_parallel_default(tmp_path, monkeypatch):
    input_file = tmp_path / "family.json"
    output_file = tmp_path / "family-result.json"
    input_file.write_text(
        json.dumps({"orbits": [{"period": 1.0}, {"period": 2.0}]}),
        encoding="utf-8",
    )
    config = _conversion.FamilyConversionConfig(
        orbit_type="halo",
        input_file=input_file,
        reference_epoch="2025-06-21T11:00:06",
        method="two_level",
        patch_points=10,
        position_tol=1e-3,
        velocity_tol=1e-6,
        spice_kernel_dir=tmp_path / "kernels",
        bodies=("EARTH", "MOON", "SUN"),
        output_file=output_file,
        per_orbit_workers=1,
        family_workers=2,
        fail_fast=False,
        include_full_trajectory=False,
    )
    submitted = []

    class FakeFuture:
        def __init__(self, result):
            self._result = result

        def result(self):
            return self._result

    class FakeProcessPoolExecutor:
        def __init__(self, max_workers):
            self.max_workers = max_workers

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def submit(self, func, payload, index, submitted_config, include_full_trajectory):
            submitted.append((func, payload, index, submitted_config, include_full_trajectory, self.max_workers))
            return FakeFuture({"index": index})

    monkeypatch.setattr(_conversion, "ProcessPoolExecutor", FakeProcessPoolExecutor)
    monkeypatch.setattr(_conversion, "as_completed", lambda futures: list(futures))

    result = _conversion.run_family_conversion(config)

    assert [call[0] for call in submitted] == [
        _conversion._convert_family_payload_with_default_adapter,
        _conversion._convert_family_payload_with_default_adapter,
    ]
    assert {call[5] for call in submitted} == {2}
    assert [entry["result"]["index"] for entry in result["results"]] == [0, 1]


def test_convert_orbit_runs_shared_pipeline_with_injected_dependencies(tmp_path):
    payload = {"states": [[1, 2, 3, 4, 5, 6]], "times": [0], "period": 1.0}
    config = _conversion.SingleConversionConfig(
        orbit_type="dro",
        input_file=tmp_path / "orbit.json",
        reference_epoch="2025-06-21T11:00:06",
        method="two_level",
        patch_points=3,
        position_tol=1e-3,
        velocity_tol=1e-6,
        spice_kernel_dir=tmp_path / "kernels",
        bodies=("EARTH", "MOON", "SUN"),
        output_file=None,
        per_orbit_workers=2,
        orbit_index=None,
    )
    orbit = SimpleNamespace(period=1.0, states=[[1, 2, 3, 4, 5, 6]])
    result = SimpleNamespace(
        converged=True,
        iterations=4,
        max_residual=1e-4,
        residual_history=[1e-2, 1e-4],
        velocity_residual=1e-7,
        velocity_residual_history=[1e-5, 1e-7],
        t_patch=[10.0, 20.0, 30.0],
        state_patch=[
            [1.0, 0.0, 0.0, 0.0, 0.1, 0.0],
            [2.0, 0.0, 0.0, 0.0, 0.1, 0.0],
            [3.0, 0.0, 0.0, 0.0, 0.1, 0.0],
        ],
    )
    dynamics = MagicMock()
    dynamics.propagate.side_effect = [
        {"states": [[1, 0, 0, 0, 0, 0], [2, 0, 0, 0, 0, 0]], "time": [10, 20]},
        {"states": [[2, 0, 0, 0, 0, 0], [3, 0, 0, 0, 0, 0]], "time": [20, 30]},
    ]
    adapter = MagicMock(spec=_conversion.EphemerisConversionAdapter)
    adapter.build_orbit.return_value = orbit
    adapter.build_dynamics.return_value = dynamics
    adapter.reference_et.return_value = 123.0
    adapter.sample_patch_points.return_value = ([0.0, 0.5, 1.0], [[1], [2], [3]])
    adapter.convert_states.return_value = ([10.0, 20.0, 30.0], [[10], [20], [30]])
    adapter.correct.return_value = result

    output = _conversion.convert_orbit(payload, config, adapter, include_full_trajectory=True)

    adapter.sample_patch_points.assert_called_once_with(orbit, 3)
    adapter.convert_states.assert_called_once()
    adapter.correct.assert_called_once()
    assert dynamics.propagate.call_count == 2
    assert output["status"] == "success"
    assert output["converged"] is True
    assert output["velocity_residual"] == 1e-7
    assert output["position_errors_km"] == [0.0, 0.0]
    assert "full_trajectory_states" in output


def test_convert_orbit_omits_full_trajectory_when_not_requested(tmp_path):
    payload = {"states": [[1, 2, 3, 4, 5, 6]], "times": [0], "period": 1.0}
    config = _conversion.SingleConversionConfig(
        orbit_type="halo",
        input_file=tmp_path / "orbit.json",
        reference_epoch="2025-06-21T11:00:06",
        method="standard",
        patch_points=2,
        position_tol=1e-3,
        velocity_tol=1e-6,
        spice_kernel_dir=tmp_path / "kernels",
        bodies=("EARTH", "MOON", "SUN"),
        output_file=None,
        per_orbit_workers=1,
        orbit_index=None,
    )
    orbit = SimpleNamespace(period=1.0, states=[[1, 2, 3, 4, 5, 6]])
    result = SimpleNamespace(
        converged=True,
        iterations=1,
        max_residual=1e-4,
        residual_history=[1e-4],
        velocity_residual=None,
        velocity_residual_history=None,
        t_patch=[10.0, 20.0],
        state_patch=[[1.0, 0, 0, 0, 0, 0], [2.0, 0, 0, 0, 0, 0]],
    )
    dynamics = MagicMock()
    dynamics.propagate.return_value = {
        "states": [[1, 0, 0, 0, 0, 0], [2, 0, 0, 0, 0, 0]],
        "time": [10, 20],
    }
    adapter = MagicMock(spec=_conversion.EphemerisConversionAdapter)
    adapter.build_orbit.return_value = orbit
    adapter.build_dynamics.return_value = dynamics
    adapter.reference_et.return_value = 123.0
    adapter.sample_patch_points.return_value = ([0.0, 1.0], [[1], [2]])
    adapter.convert_states.return_value = ([10.0, 20.0], [[10], [20]])
    adapter.correct.return_value = result

    output = _conversion.convert_orbit(payload, config, adapter, include_full_trajectory=False)

    assert output["velocity_residual"] is None
    assert "full_trajectory_states" not in output
    assert "full_trajectory_times_et" not in output


def test_convert_orbit_marks_not_converged_when_corrector_does_not_converge(tmp_path):
    payload = {"states": [[1, 2, 3, 4, 5, 6]], "times": [0], "period": 1.0}
    config = _conversion.SingleConversionConfig(
        orbit_type="dro",
        input_file=tmp_path / "orbit.json",
        reference_epoch="2025-06-21T11:00:06",
        method="two_level",
        patch_points=2,
        position_tol=1e-3,
        velocity_tol=1e-6,
        spice_kernel_dir=tmp_path / "kernels",
        bodies=("EARTH", "MOON", "SUN"),
        output_file=None,
        per_orbit_workers=1,
        orbit_index=None,
    )
    orbit = SimpleNamespace(period=1.0, states=[[1, 2, 3, 4, 5, 6]])
    result = SimpleNamespace(
        converged=False,
        iterations=10,
        max_residual=1.0,
        residual_history=[1.0],
        velocity_residual=None,
        velocity_residual_history=None,
        t_patch=[10.0, 20.0],
        state_patch=[[1.0, 0, 0, 0, 0, 0], [2.0, 0, 0, 0, 0, 0]],
    )
    dynamics = MagicMock()
    dynamics.propagate.return_value = {
        "states": [[1, 0, 0, 0, 0, 0], [2, 0, 0, 0, 0, 0]],
        "time": [10, 20],
    }
    adapter = MagicMock(spec=_conversion.EphemerisConversionAdapter)
    adapter.build_orbit.return_value = orbit
    adapter.build_dynamics.return_value = dynamics
    adapter.reference_et.return_value = 123.0
    adapter.sample_patch_points.return_value = ([0.0, 1.0], [[1], [2]])
    adapter.convert_states.return_value = ([10.0, 20.0], [[10], [20]])
    adapter.correct.return_value = result

    output = _conversion.convert_orbit(payload, config, adapter, include_full_trajectory=False)

    assert output["status"] == "not_converged"
    assert output["converged"] is False
    assert output["max_residual"] == 1.0
    assert output["residual_history"] == [1.0]
    assert output["position_errors_km"] == [0.0]
    assert output["source_summary"] is not None


def test_run_family_payload_conversion_records_not_converged_and_continues():
    not_converged_result = {"status": "not_converged", "converged": False}

    def convert(payload, index, include_full_trajectory):
        if index == 1:
            return not_converged_result
        return {"status": "success", "converged": True}

    result = _conversion.run_family_payload_conversion(
        [{"period": 1.0}, {"period": 2.0}, {"period": 3.0}],
        convert,
        fail_fast=False,
        include_full_trajectory=False,
    )

    assert [entry["orbit_index"] for entry in result] == [0, 1, 2]
    assert result[0]["status"] == "success"
    assert result[1]["status"] == "not_converged"
    assert result[1]["result"] == not_converged_result
    assert result[2]["status"] == "success"


def test_run_family_payload_conversion_fail_fast_stops_after_not_converged():
    not_converged_result = {"status": "not_converged", "converged": False}

    def convert(payload, index, include_full_trajectory):
        if index == 1:
            return not_converged_result
        return {"status": "success", "converged": True}

    result = _conversion.run_family_payload_conversion(
        [{"period": 1.0}, {"period": 2.0}, {"period": 3.0}],
        convert,
        fail_fast=True,
        include_full_trajectory=False,
    )

    assert [entry["status"] for entry in result] == ["success", "not_converged"]
    assert len(result) == 2


def test_run_family_payload_conversion_parallel_records_not_converged_in_input_order():
    not_converged_result = {"status": "not_converged", "converged": False}

    def convert(payload, index, include_full_trajectory):
        if index == 1:
            return not_converged_result
        return {"status": "success", "converged": True}

    result = _conversion.run_family_payload_conversion(
        [{"period": 1.0}, {"period": 2.0}, {"period": 3.0}],
        convert,
        fail_fast=False,
        include_full_trajectory=False,
        family_workers=2,
    )

    assert [entry["orbit_index"] for entry in result] == [0, 1, 2]
    assert [entry["status"] for entry in result] == ["success", "not_converged", "success"]
