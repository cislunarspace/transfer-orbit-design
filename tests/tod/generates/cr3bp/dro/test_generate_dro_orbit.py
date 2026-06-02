from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest


def _write_dro_catalog(catalog_dir: Path) -> None:
    catalog_dir.mkdir(parents=True)
    families_dir = catalog_dir / "families"
    families_dir.mkdir()
    with (catalog_dir / "index.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["dataset_id", "orbit_type", "family_csv"])
        writer.writeheader()
        writer.writerow({"dataset_id": "earth-moon_dro", "orbit_type": "dro", "family_csv": "families/dro.csv"})
    fieldnames = [
        "orbit_id", "dataset_id", "system", "source_orbit_type", "orbit_type", "variant",
        "libration_point", "branch", "resonance", "source_file", "source_row",
        "x", "y", "z", "vx", "vy", "vz", "jacobi", "period", "stability",
        "mu", "length_unit_km", "time_unit_s", "radius_secondary", "script_status",
    ]
    with (families_dir / "dro.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow({
            "orbit_id": "earth-moon_dro:000001", "dataset_id": "earth-moon_dro",
            "system": "earth-moon", "source_orbit_type": "dro", "orbit_type": "dro",
            "variant": "", "libration_point": "", "branch": "", "resonance": "",
            "source_file": "earth-moon_dro.xlsx", "source_row": "2",
            "x": "1", "y": "2", "z": "3", "vx": "4", "vy": "5", "vz": "6",
            "jacobi": "3.1", "period": "7", "stability": "8", "mu": "0.01215",
            "length_unit_km": "389703", "time_unit_s": "382981", "radius_secondary": "1737.1",
            "script_status": "supported",
        })


class FakeSystem:
    pass


class FakeDynamics:
    def equations_of_motion(self, t, state):
        return state


def test_catalog_propagation_rejects_failed_integration(monkeypatch) -> None:
    """catalog propagation must not save a truncated solve_ivp result as a DRO."""
    import tod.generates.cr3bp.dro.generate_dro_orbit as mod

    class FailedResult:
        success = False
        message = "required step size is less than spacing between numbers"
        t = [0.0]
        y = [[1.0], [2.0], [3.0], [4.0], [5.0], [6.0]]

    monkeypatch.setattr(mod.sci_integrate, "solve_ivp", lambda *args, **kwargs: FailedResult())

    with pytest.raises(RuntimeError, match="catalog seed propagation failed"):
        mod._propagate_catalog_seed([1.0, 2.0, 3.0, 4.0, 5.0, 6.0], 7.0, FakeDynamics())


def test_catalog_path_can_disable_auto_build(monkeypatch, tmp_path: Path) -> None:
    """--no-auto-build-catalog fails clearly instead of importing raw data."""
    import tod.generates.cr3bp.dro.generate_dro_orbit as mod

    def fail_import(*args, **kwargs):
        raise AssertionError("auto-build must be disabled")

    monkeypatch.setattr(mod.e2m2e.core.system, "CR3BP_System", lambda **kwargs: FakeSystem())
    monkeypatch.setattr(mod.e2m2e.core.dynamics, "CR3BP_Dynamics", lambda **kwargs: FakeDynamics())
    monkeypatch.setattr(mod, "import_cr3bp_xlsx_catalog", fail_import)

    with pytest.raises(SystemExit, match="normalized CR3BP catalog 缺失"):
        mod.main([
            "--seed-id", "earth-moon_dro:000001",
            "--catalog-dir", str(tmp_path / "missing"),
            "--no-auto-build-catalog",
        ])


def test_catalog_path_auto_builds_normalized_catalog_when_missing(monkeypatch, tmp_path: Path) -> None:
    """missing normalized catalog is generated from raw data before lookup."""
    import tod.generates.cr3bp.dro.generate_dro_orbit as mod

    catalog_dir = tmp_path / "normalized"
    raw_dir = tmp_path / "raw"
    output_dir = tmp_path / "out"
    calls: list[tuple[Path, Path]] = []
    saved_files: list[Path] = []

    class FakeOrbit:
        def __init__(self, states, times):
            self.states = states
            self.times = times
            self.period = None
            self.metadata: dict[str, object] = {}

        def save_to_file(self, filename: str) -> None:
            path = Path(filename)
            saved_files.append(path)
            path.write_text(json.dumps({"metadata": self.metadata}), encoding="utf-8")

    def fake_import(raw_data_dir, normalized_dir, *, overwrite=False):
        assert overwrite is False
        calls.append((raw_data_dir, normalized_dir))
        _write_dro_catalog(normalized_dir)

    def fake_propagate(initial_state, period, dynamics, **kwargs):
        orbit = FakeOrbit([initial_state], [0.0])
        orbit.period = period
        return orbit

    monkeypatch.setattr(mod, "OUTPUT_DIR", output_dir)
    monkeypatch.setattr(mod.time, "time", lambda: 1234567890)
    monkeypatch.setattr(mod.e2m2e.core.system, "CR3BP_System", lambda **kwargs: FakeSystem())
    monkeypatch.setattr(mod.e2m2e.core.dynamics, "CR3BP_Dynamics", lambda **kwargs: FakeDynamics())
    monkeypatch.setattr(mod, "import_cr3bp_xlsx_catalog", fake_import)
    monkeypatch.setattr(mod, "_propagate_catalog_seed", fake_propagate)

    mod.main(["--seed-id", "earth-moon_dro:000001", "--catalog-dir", str(catalog_dir), "--raw-data-dir", str(raw_dir)])

    assert calls == [(raw_dir, catalog_dir)]
    assert saved_files == [output_dir / "dro_catalog_earth-moon_dro_000001_1234567890.json"]


def test_jacobi_path_records_match_metadata(monkeypatch, tmp_path: Path) -> None:
    """Jacobi catalog lookup records target/actual/error/tolerance provenance."""
    import tod.generates.cr3bp.dro.generate_dro_orbit as mod

    catalog_dir = tmp_path / "normalized"
    output_dir = tmp_path / "out"
    _write_dro_catalog(catalog_dir)
    saved_files: list[Path] = []

    class FakeOrbit:
        def __init__(self, states, times):
            self.states = states
            self.times = times
            self.period = None
            self.metadata: dict[str, object] = {}

        def save_to_file(self, filename: str) -> None:
            path = Path(filename)
            saved_files.append(path)
            path.write_text(json.dumps({"metadata": self.metadata}), encoding="utf-8")

    def fake_propagate(initial_state, period, dynamics, **kwargs):
        orbit = FakeOrbit([initial_state], [0.0])
        orbit.period = period
        return orbit

    monkeypatch.setattr(mod, "OUTPUT_DIR", output_dir)
    monkeypatch.setattr(mod.time, "time", lambda: 1234567890)
    monkeypatch.setattr(mod.e2m2e.core.system, "CR3BP_System", lambda **kwargs: FakeSystem())
    monkeypatch.setattr(mod.e2m2e.core.dynamics, "CR3BP_Dynamics", lambda **kwargs: FakeDynamics())
    monkeypatch.setattr(mod, "_propagate_catalog_seed", fake_propagate)

    mod.main(["--jacobi", "3.10005", "--jacobi-tolerance", "0.001", "--catalog-dir", str(catalog_dir)])

    metadata = json.loads(saved_files[0].read_text(encoding="utf-8"))["metadata"]
    assert metadata["seed_source"] == "catalog_jacobi"
    assert metadata["target"] == 3.10005
    assert metadata["actual"] == 3.1
    assert metadata["error"] == pytest.approx(0.00005)
    assert metadata["tolerance"] == 0.001
    assert metadata["source_file"] == "earth-moon_dro.xlsx"
    assert metadata["source_row"] == 2


def test_jacobi_path_defaults_to_no_hard_tolerance(monkeypatch, tmp_path: Path) -> None:
    """Jacobi mode chooses the nearest seed by default even when the delta is large."""
    import tod.generates.cr3bp.dro.generate_dro_orbit as mod

    catalog_dir = tmp_path / "normalized"
    output_dir = tmp_path / "out"
    _write_dro_catalog(catalog_dir)
    saved_files: list[Path] = []

    class FakeOrbit:
        def __init__(self, states, times):
            self.states = states
            self.times = times
            self.period = None
            self.metadata: dict[str, object] = {}

        def save_to_file(self, filename: str) -> None:
            path = Path(filename)
            saved_files.append(path)
            path.write_text(json.dumps({"metadata": self.metadata}), encoding="utf-8")

    def fake_propagate(initial_state, period, dynamics, **kwargs):
        orbit = FakeOrbit([initial_state], [0.0])
        orbit.period = period
        return orbit

    monkeypatch.setattr(mod, "OUTPUT_DIR", output_dir)
    monkeypatch.setattr(mod.time, "time", lambda: 1234567890)
    monkeypatch.setattr(mod.e2m2e.core.system, "CR3BP_System", lambda **kwargs: FakeSystem())
    monkeypatch.setattr(mod.e2m2e.core.dynamics, "CR3BP_Dynamics", lambda **kwargs: FakeDynamics())
    monkeypatch.setattr(mod, "_propagate_catalog_seed", fake_propagate)

    mod.main(["--jacobi", "0.0", "--catalog-dir", str(catalog_dir)])

    metadata = json.loads(saved_files[0].read_text(encoding="utf-8"))["metadata"]
    assert metadata["seed_source"] == "catalog_jacobi"
    assert metadata["target"] == 0.0
    assert metadata["actual"] == 3.1
    assert metadata["error"] == pytest.approx(3.1)
    assert metadata["tolerance"] is None
    assert metadata["selection_mode"] == "jacobi"
    assert metadata["matched_seed_id"] == "earth-moon_dro:000001"
    assert metadata["target_jacobi"] == 0.0
    assert metadata["matched_jacobi"] == 3.1
    assert metadata["jacobi_delta"] == pytest.approx(3.1)


def test_catalog_csv_errors_are_reported_as_cli_friendly_system_exit(monkeypatch, tmp_path: Path) -> None:
    """invalid normalized catalog data should not leak a raw importer traceback to GUI jobs."""
    import tod.generates.cr3bp.dro.generate_dro_orbit as mod

    catalog_dir = tmp_path / "normalized"
    _write_dro_catalog(catalog_dir)
    dro_csv = catalog_dir / "families" / "dro.csv"
    with dro_csv.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
        fieldnames = list(rows[0].keys())
    rows[0]["x"] = "nan"
    with dro_csv.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    monkeypatch.setattr(mod.e2m2e.core.system, "CR3BP_System", lambda **kwargs: FakeSystem())
    monkeypatch.setattr(mod.e2m2e.core.dynamics, "CR3BP_Dynamics", lambda **kwargs: FakeDynamics())

    with pytest.raises(SystemExit, match="catalog CSV.*earth-moon_dro:000001.*x"):
        mod.main(["--seed-id", "earth-moon_dro:000001", "--catalog-dir", str(catalog_dir)])


def test_catalog_seed_id_path_propagates_without_correction(monkeypatch, tmp_path: Path) -> None:
    """catalog seed path uses full 6D state + period and skips differential correction."""
    import tod.generates.cr3bp.dro.generate_dro_orbit as mod

    catalog_dir = tmp_path / "normalized"
    output_dir = tmp_path / "out"
    _write_dro_catalog(catalog_dir)
    saved_files: list[Path] = []

    propagated_options: list[dict[str, object]] = []

    class FakeOrbit:
        def __init__(self, states, times):
            self.states = states
            self.times = times
            self.period = None
            self.metadata: dict[str, object] = {}

        def save_to_file(self, filename: str) -> None:
            path = Path(filename)
            saved_files.append(path)
            path.write_text(json.dumps({"states": self.states, "times": self.times, "metadata": self.metadata}), encoding="utf-8")

    class FailingCorrector:
        def __init__(self, dynamic):
            raise AssertionError("catalog path must not run differential correction")

    def fake_propagate(initial_state, period, dynamics, **kwargs):
        propagated_options.append({"period": period, **kwargs})
        orbit = FakeOrbit([initial_state], [0.0, 14.0])
        orbit.period = period * kwargs["period_multiplier"]
        return orbit

    monkeypatch.setattr(mod, "OUTPUT_DIR", output_dir)
    monkeypatch.setattr(mod.time, "time", lambda: 1234567890)
    monkeypatch.setattr(mod.e2m2e.core.system, "CR3BP_System", lambda **kwargs: FakeSystem())
    monkeypatch.setattr(mod.e2m2e.core.dynamics, "CR3BP_Dynamics", lambda **kwargs: FakeDynamics())
    monkeypatch.setattr(mod.e2m2e.algorithms, "DifferentialCorrection", FailingCorrector)
    monkeypatch.setattr(mod, "_propagate_catalog_seed", fake_propagate)

    mod.main([
        "--seed-id", "earth-moon_dro:000001",
        "--catalog-dir", str(catalog_dir),
        "--period-multiplier", "2.0",
        "--num-points", "2",
    ])

    assert propagated_options == [{"period": 7.0, "period_multiplier": 2.0, "num_points": 2}]
    assert saved_files == [output_dir / "dro_catalog_earth-moon_dro_000001_1234567890.json"]
    payload = json.loads(saved_files[0].read_text(encoding="utf-8"))
    assert payload["states"] == [[1.0, 2.0, 3.0, 4.0, 5.0, 6.0]]
    assert payload["metadata"]["seed_source"] == "catalog_seed_id"
    assert payload["metadata"]["selection_mode"] == "seed_id"
    assert payload["metadata"]["matched_seed_id"] == "earth-moon_dro:000001"
    assert payload["metadata"]["seed_id"] == "earth-moon_dro:000001"
    assert payload["metadata"]["initial_state"] == [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    assert payload["metadata"]["period"] == 7.0
    assert payload["metadata"]["period_multiplier"] == 2.0
    assert payload["metadata"]["propagation_duration"] == 14.0
    assert payload["metadata"]["num_points"] == 2
    assert payload["metadata"]["integrator"] == "DOP853"
    assert payload["metadata"]["rtol"] == 1e-12
    assert payload["metadata"]["atol"] == 1e-12
    assert payload["metadata"]["is_corrected"] is False
    assert payload["metadata"]["generation_method"] == "catalog_seed_propagation"


def test_parser_exposes_catalog_seed_arguments() -> None:
    """catalog seed path can be selected by Jacobi with default tolerance/catalog dir."""
    import tod.generates.cr3bp.dro.generate_dro_orbit as mod

    args = mod.parse_args(["--jacobi", "2.95"])

    assert args.jacobi == 2.95
    assert args.seed_id is None
    assert args.jacobi_tolerance is None
    assert str(args.catalog_dir) == "data/cr3bp_data/normalized"


def test_parser_exposes_manual_defaults() -> None:
    """raw parser leaves manual seed unset so catalog mode can detect explicit overrides."""
    import tod.generates.cr3bp.dro.generate_dro_orbit as mod

    args = mod.parse_args([])

    assert args.x0 is None
    assert args.vy0 is None
    assert args.period is None
    assert mod.DEFAULT_DRO_X0 == 1.1202
    assert mod.DEFAULT_DRO_VY0 == -0.4618
    assert mod.DEFAULT_DRO_PERIOD == 2.095


def test_parser_exposes_period_multiplier_and_num_points_bounds() -> None:
    """catalog propagation controls expose safe defaults and reject invalid ranges."""
    import tod.generates.cr3bp.dro.generate_dro_orbit as mod

    args = mod.parse_args([])
    assert args.period_multiplier == 1.0
    assert args.num_points == 1000

    valid = mod.parse_args(["--period-multiplier", "2.5", "--num-points", "2"])
    assert valid.period_multiplier == 2.5
    assert valid.num_points == 2

    valid_upper = mod.parse_args(["--num-points", "100000"])
    assert valid_upper.num_points == 100000

    for argv in (["--period-multiplier", "0"], ["--period-multiplier", "-1"], ["--num-points", "1"], ["--num-points", "100001"]):
        with pytest.raises(SystemExit):
            mod.parse_args(argv)


def test_catalog_mode_rejects_explicit_manual_seed_arguments(tmp_path: Path) -> None:
    """catalog selection cannot be mixed with explicit manual x0/vy0/period overrides."""
    import tod.generates.cr3bp.dro.generate_dro_orbit as mod

    with pytest.raises(SystemExit, match="--seed-id.*--period"):
        mod.main([
            "--seed-id", "earth-moon_dro:000001",
            "--period", "3.0",
            "--catalog-dir", str(tmp_path / "missing"),
        ])


def test_manual_path_corrects_and_saves_dro_json_metadata(monkeypatch, tmp_path: Path) -> None:
    """manual seed path writes the renamed single-DRO artifact with provenance."""
    import tod.generates.cr3bp.dro.generate_dro_orbit as mod

    saved_files: list[Path] = []

    class FakeOrbit:
        def __init__(self, states, times):
            self.states = states
            self.times = times
            self.period = 2.5
            self.metadata: dict[str, object] = {}

        def save_to_file(self, filename: str) -> None:
            path = Path(filename)
            saved_files.append(path)
            path.write_text(
                json.dumps(
                    {
                        "states": self.states,
                        "times": self.times,
                        "properties": {"period": self.period},
                        "metadata": self.metadata,
                    }
                ),
                encoding="utf-8",
            )

    class FakeCorrector:
        termination_reason = "not run"

        def __init__(self, dynamic):
            self.dynamic = dynamic
            self.t_half = None

        def setup_2D_symmetric_x_fixed_t(self, t_half):
            self.t_half = t_half

        def iterate_correction(self, initial_guess, verbose=False, callback=None):
            assert initial_guess.states == [[1.2, 0.0, 0.0, 0.0, -0.4, 0.0]]
            assert self.t_half == 1.75
            result = FakeOrbit([[1.2, 0.0, 0.0, 0.0, -0.4, 0.0]], [0.0])
            result.period = 3.5
            return result

    monkeypatch.setattr(mod, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(mod.time, "time", lambda: 1234567890)
    monkeypatch.setattr(mod, "Orbit", FakeOrbit)
    monkeypatch.setattr(mod.e2m2e.core.system, "CR3BP_System", lambda **kwargs: object())
    monkeypatch.setattr(mod.e2m2e.core.dynamics, "CR3BP_Dynamics", lambda **kwargs: object())
    monkeypatch.setattr(mod.e2m2e.algorithms, "DifferentialCorrection", FakeCorrector)

    mod.main(["--x0", "1.2", "--vy0", "-0.4", "--period", "3.5"])

    output_file = tmp_path / "dro_1234567890.json"
    assert saved_files == [output_file]
    assert not (tmp_path / "dro_31_1234567890.json").exists()

    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert payload["metadata"] == {
        "seed_source": "manual",
        "initial_state": [1.2, 0.0, 0.0, 0.0, -0.4, 0.0],
        "period": 3.5,
        "is_corrected": True,
        "generation_method": "fixed_period_differential_correction",
    }
    assert payload["properties"]["period"] == 3.5
