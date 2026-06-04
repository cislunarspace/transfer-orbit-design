from __future__ import annotations

import csv
import json
import time
from pathlib import Path

import pytest


def _write_dpo_catalog(catalog_dir: Path) -> None:
    catalog_dir.mkdir(parents=True)
    families_dir = catalog_dir / "families"
    families_dir.mkdir()
    with (catalog_dir / "index.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["dataset_id", "orbit_type", "family_csv"])
        writer.writeheader()
        writer.writerow({"dataset_id": "earth-moon_dpo", "orbit_type": "dpo", "family_csv": "families/dpo.csv"})
    fieldnames = [
        "orbit_id", "dataset_id", "system", "source_orbit_type", "orbit_type", "variant",
        "libration_point", "branch", "resonance", "source_file", "source_row",
        "x", "y", "z", "vx", "vy", "vz", "jacobi", "period", "stability",
        "mu", "length_unit_km", "time_unit_s", "radius_secondary", "script_status",
    ]
    with (families_dir / "dpo.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow({
            "orbit_id": "earth-moon_dpo:000001", "dataset_id": "earth-moon_dpo",
            "system": "earth-moon", "source_orbit_type": "dpo", "orbit_type": "dpo",
            "variant": "", "libration_point": "", "branch": "", "resonance": "",
            "source_file": "earth-moon_dpo.xlsx", "source_row": "2",
            "x": "1.03774", "y": "0", "z": "0", "vx": "0", "vy": "0.503284", "vz": "0",
            "jacobi": "3.19", "period": "1.2011", "stability": "0",
            "mu": "0.01215", "length_unit_km": "389703", "time_unit_s": "382981",
            "radius_secondary": "1737.1", "script_status": "supported",
        })


class FakeSystem:
    pass


class FakeDynamics:
    def equations_of_motion(self, t, state):
        return state


class FakeOrbit:
    def __init__(self, states, times):
        self.states = states
        self.times = times
        self.period = None
        self.metadata: dict[str, object] = {}

    def save_to_file(self, filename: str) -> None:
        path = Path(filename)
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


def test_manual_path_corrects_and_saves_dpo_json_metadata(monkeypatch, tmp_path: Path) -> None:
    """manual seed path writes the renamed single-DPO artifact with provenance."""
    import tod.generates.cr3bp.dpo.generate_dpo_orbit as mod

    saved_files: list[Path] = []

    class FakeCorrector:
        termination_reason = "not run"

        def __init__(self, dynamic):
            self.dynamic = dynamic
            self.t_half = None

        def setup_2D_symmetric_x_fixed_t(self, t_half):
            self.t_half = t_half

        def iterate_correction(self, initial_guess, verbose=False, callback=None):
            state = initial_guess.states[0]
            assert state[1] == 0.0 and state[2] == 0.0 and state[3] == 0.0 and state[5] == 0.0
            assert state[4] > 0, "DPO initial vy0 should be positive"
            result = FakeOrbit([state], [0.0])
            result.period = 2.5
            return result

    def fake_save(orbit, metadata, **kwargs):
        path = tmp_path / f"dpo_{int(1234567890)}.json"
        saved_files.append(path)
        orbit.metadata.update(metadata)
        path.write_text(
            json.dumps(
                {
                    "states": orbit.states,
                    "times": orbit.times,
                    "properties": {"period": orbit.period},
                    "metadata": orbit.metadata,
                }
            ),
            encoding="utf-8",
        )
        return path

    monkeypatch.setattr(mod, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(mod.time, "time", lambda: 1234567890)
    monkeypatch.setattr(mod, "Orbit", FakeOrbit)
    monkeypatch.setattr(mod.e2m2e.core.system, "CR3BP_System", lambda **kwargs: object())
    monkeypatch.setattr(mod.e2m2e.core.dynamics, "CR3BP_Dynamics", lambda **kwargs: object())
    monkeypatch.setattr(mod.e2m2e.algorithms, "DifferentialCorrection", FakeCorrector)
    monkeypatch.setattr(mod, "_save_orbit", fake_save)

    mod.main(["--x0", "1.03774", "--vy0", "0.503284", "--period", "1.2011"])

    assert len(saved_files) == 1
    payload = json.loads(saved_files[0].read_text(encoding="utf-8"))
    assert payload["metadata"]["seed_source"] == "manual"
    assert payload["metadata"]["is_corrected"] is True
    assert payload["metadata"]["generation_method"] == "fixed_period_differential_correction"
    state = payload["metadata"]["initial_state"]
    assert state == [1.03774, 0.0, 0.0, 0.0, 0.503284, 0.0]
    assert state[4] > 0


def test_catalog_propagation_rejects_failed_integration(monkeypatch) -> None:
    """catalog propagation must not save a truncated solve_ivp result as a DPO."""
    import tod.generates.cr3bp.dpo.generate_dpo_orbit as mod

    class FailedResult:
        success = False
        message = "required step size is less than spacing between numbers"
        t = [0.0]
        y = [[1.0], [2.0], [3.0], [4.0], [5.0], [6.0]]

    monkeypatch.setattr(mod.sci_integrate, "solve_ivp", lambda *args, **kwargs: FailedResult())

    with pytest.raises(RuntimeError, match="catalog seed propagation failed"):
        mod._propagate_catalog_seed([1.03774, 0.0, 0.0, 0.0, 0.503284, 0.0], 1.2011, FakeDynamics())


def test_catalog_seed_id_path_propagates_without_correction(monkeypatch, tmp_path: Path) -> None:
    """catalog seed path uses full 6D state + period and skips differential correction."""
    import tod.generates.cr3bp.dpo.generate_dpo_orbit as mod

    catalog_dir = tmp_path / "normalized"
    output_dir = tmp_path / "out"
    _write_dpo_catalog(catalog_dir)
    saved_files: list[Path] = []

    propagated_options: list[dict[str, object]] = []

    class FailingCorrector:
        def __init__(self, dynamic):
            raise AssertionError("catalog path must not run differential correction")

    def fake_propagate(initial_state, period, dynamics, **kwargs):
        propagated_options.append({"period": period, **kwargs})
        orbit = FakeOrbit([initial_state], [0.0, 14.0])
        orbit.period = period * kwargs["period_multiplier"]
        return orbit

    def fake_save(orbit, metadata, **kwargs):
        orbit.metadata.update(metadata)
        seed_id = kwargs.get("seed_id")
        filename = f"dpo_catalog_{seed_id}_{int(time.time())}.json"
        output_file = output_dir / filename
        output_dir.mkdir(parents=True, exist_ok=True)
        saved_files.append(output_file)
        output_file.write_text(
            json.dumps({"states": orbit.states, "times": orbit.times, "metadata": orbit.metadata}),
            encoding="utf-8",
        )
        return output_file

    monkeypatch.setattr(mod, "OUTPUT_DIR", output_dir)
    monkeypatch.setattr(mod.time, "time", lambda: 1234567890)
    monkeypatch.setattr(mod.e2m2e.core.system, "CR3BP_System", lambda **kwargs: FakeSystem())
    monkeypatch.setattr(mod.e2m2e.core.dynamics, "CR3BP_Dynamics", lambda **kwargs: FakeDynamics())
    monkeypatch.setattr(mod.e2m2e.algorithms, "DifferentialCorrection", FailingCorrector)
    monkeypatch.setattr(mod, "_propagate_catalog_seed", fake_propagate)
    monkeypatch.setattr(mod, "_save_orbit", fake_save)

    mod.main([
        "--seed-id", "earth-moon_dpo:000001",
        "--catalog-dir", str(catalog_dir),
        "--period-multiplier", "2.0",
        "--num-points", "2",
    ])

    assert propagated_options == [{"period": 1.2011, "period_multiplier": 2.0, "num_points": 2}]
    assert len(saved_files) == 1
    payload = json.loads(saved_files[0].read_text(encoding="utf-8"))
    assert payload["states"] == [[1.03774, 0.0, 0.0, 0.0, 0.503284, 0.0]]
    assert payload["metadata"]["seed_source"] == "catalog_seed_id"
    assert payload["metadata"]["selection_mode"] == "seed_id"
    assert payload["metadata"]["matched_seed_id"] == "earth-moon_dpo:000001"
    assert payload["metadata"]["seed_id"] == "earth-moon_dpo:000001"
    assert payload["metadata"]["initial_state"] == [1.03774, 0.0, 0.0, 0.0, 0.503284, 0.0]
    assert payload["metadata"]["period"] == 1.2011
    assert payload["metadata"]["period_multiplier"] == 2.0
    assert payload["metadata"]["propagation_duration"] == pytest.approx(1.2011 * 2.0)
    assert payload["metadata"]["num_points"] == 2
    assert payload["metadata"]["integrator"] == "DOP853"
    assert payload["metadata"]["rtol"] == 1e-12
    assert payload["metadata"]["atol"] == 1e-12
    assert payload["metadata"]["is_corrected"] is False
    assert payload["metadata"]["generation_method"] == "catalog_seed_propagation"


def test_jacobi_path_records_match_metadata(monkeypatch, tmp_path: Path) -> None:
    """Jacobi catalog lookup records target/actual/error/tolerance provenance."""
    import tod.generates.cr3bp.dpo.generate_dpo_orbit as mod

    catalog_dir = tmp_path / "normalized"
    output_dir = tmp_path / "out"
    _write_dpo_catalog(catalog_dir)
    saved_files: list[Path] = []

    def fake_propagate(initial_state, period, dynamics, **kwargs):
        orbit = FakeOrbit([initial_state], [0.0])
        orbit.period = period
        return orbit

    def fake_save(orbit, metadata, **kwargs):
        orbit.metadata.update(metadata)
        ts = int(time.time())
        seed_id = kwargs.get("seed_id")
        if seed_id is None:
            filename = f"dpo_{ts}.json"
        else:
            filename = f"dpo_catalog_{ts}.json"
        output_file = output_dir / filename
        output_dir.mkdir(parents=True, exist_ok=True)
        saved_files.append(output_file)
        output_file.write_text(json.dumps({"metadata": orbit.metadata}), encoding="utf-8")
        return output_file

    monkeypatch.setattr(mod, "OUTPUT_DIR", output_dir)
    monkeypatch.setattr(mod.time, "time", lambda: 1234567890)
    monkeypatch.setattr(mod.e2m2e.core.system, "CR3BP_System", lambda **kwargs: FakeSystem())
    monkeypatch.setattr(mod.e2m2e.core.dynamics, "CR3BP_Dynamics", lambda **kwargs: FakeDynamics())
    monkeypatch.setattr(mod, "_propagate_catalog_seed", fake_propagate)
    monkeypatch.setattr(mod, "_save_orbit", fake_save)

    mod.main(["--jacobi", "3.19005", "--jacobi-tolerance", "0.001", "--catalog-dir", str(catalog_dir)])

    metadata = json.loads(saved_files[0].read_text(encoding="utf-8"))["metadata"]
    assert metadata["seed_source"] == "catalog_jacobi"
    assert metadata["target"] == 3.19005
    assert metadata["actual"] == 3.19
    assert metadata["error"] == pytest.approx(0.00005)
    assert metadata["tolerance"] == 0.001
    assert metadata["raw_source_path"] == "earth-moon_dpo.xlsx"
    assert metadata["raw_source_row"] == 2
    assert metadata["normalized_catalog_dir"].endswith("normalized")


def test_catalog_mode_rejects_explicit_manual_seed_arguments(tmp_path: Path) -> None:
    """catalog selection cannot be mixed with explicit manual x0/vy0/period overrides."""
    import tod.generates.cr3bp.dpo.generate_dpo_orbit as mod

    with pytest.raises(SystemExit, match="--seed-id.*--period"):
        mod.main([
            "--seed-id", "earth-moon_dpo:000001",
            "--period", "3.0",
            "--catalog-dir", str(tmp_path / "missing"),
        ])


def test_parser_exposes_manual_defaults() -> None:
    """raw parser leaves manual seed unset so catalog mode can detect explicit overrides."""
    import tod.generates.cr3bp.dpo.generate_dpo_orbit as mod

    args = mod.parse_args([])

    assert args.x0 is None
    assert args.vy0 is None
    assert args.period is None
    assert mod.DEFAULT_DPO_X0 == 1.03774
    assert mod.DEFAULT_DPO_VY0 == 0.503284
    assert mod.DEFAULT_DPO_PERIOD == 1.2011


def test_jacobi_strict_tolerance_failure_reports_match_context(tmp_path: Path) -> None:
    """strict Jacobi tolerance fails fast with target, matched seed, delta, and tolerance."""
    import tod.generates.cr3bp.dpo.generate_dpo_orbit as mod

    catalog_dir = tmp_path / "normalized"
    _write_dpo_catalog(catalog_dir)

    with pytest.raises(SystemExit) as exc_info:
        mod.main(["--jacobi", "0.0", "--jacobi-tolerance", "0.1", "--catalog-dir", str(catalog_dir)])

    message = str(exc_info.value)
    assert "Jacobi strict tolerance exceeded" in message
    assert "target=0.0" in message
    assert "delta=" in message
    assert "tolerance=0.1" in message
