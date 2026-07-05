"""End-to-end / regression tests for DRO catalog GUI → CLI → plot consumer.

Covers:
- #178: GUI Jacobi args can drive the CLI and produce matched seed/delta in
  metadata (and log) for both default and strict tolerance paths.
- #179: GUI Seed ID args can drive the CLI; catalog outputs use the same
  filename helper as manual mode; both catalog outputs are readable by the
  plot consumer.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication, QComboBox, QLineEdit

from tod.scripting import CatalogSeedSelectorParam, CliParam, ScriptEntry


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


import csv  # placed after helper for readability


def _make_dro_entry() -> ScriptEntry:
    return ScriptEntry(
        module="dro",
        name="generate_dro_orbit",
        description="生成 DRO 轨道",
        script_path="tod/generates/cr3bp/dro/generate_dro_orbit.py",
        output_dir="output/dro",
        group_label="生成",
        catalog_seed_selectors=[
            CatalogSeedSelectorParam(
                key="dro_catalog_seed",
                label="DRO 参考初值",
                orbit_type="dro",
                manual_flags=("--x0", "--vy0", "--period"),
            ),
        ],
        cli_params=[
            CliParam("--x0", "初始 x 坐标", "float", "1.1202"),
            CliParam("--vy0", "初始 vy 速度", "float", "-0.4618"),
            CliParam("--period", "目标周期", "float", "2.095"),
            CliParam("--jacobi", "Jacobi", "float", ""),
            CliParam("--seed-id", "参考记录编号", "str", ""),
            CliParam("--jacobi-tolerance", "Jacobi 容差", "float", ""),
            CliParam("--catalog-dir", "参考数据集目录", "str", "data/cr3bp_data/normalized"),
        ],
    )


@pytest.fixture
def qapp_fixture():
    return QApplication.instance() or QApplication([])


class TestGuiJacobiDrivesCliRegression:
    def test_gui_jacobi_args_drive_cli_with_matched_seed_and_delta(self, qapp_fixture, tmp_path, monkeypatch):
        from tod.gui.script_tab_widget import ScriptTabWidget
        import tod.generates.cr3bp.dro.generate_dro_orbit as mod

        catalog_dir = tmp_path / "normalized"
        _write_dro_catalog(catalog_dir)
        output_dir = tmp_path / "out"

        widget = ScriptTabWidget(
            entry=_make_dro_entry(), files=[], repo_root=tmp_path,
            gui_defaults={}, theme_mode="system",
        )
        state = widget._catalog_seed_selectors["dro_catalog_seed"]
        state.enabled_checkbox.setChecked(True)
        state.mode_widget.setCurrentIndex(state.mode_widget.findData("jacobi_match"))
        state.jacobi_widget.setText("3.10005")
        state.tolerance_widget.setText("1e-3")

        cli_args = widget.collect_run_args()
        assert "--jacobi" in cli_args
        assert "--jacobi-tolerance" in cli_args

        class FakeOrbit:
            def __init__(self, states, times):
                self.states = states
                self.times = times
                self.period = None
                self.metadata: dict[str, object] = {}

            def save_to_file(self, filename: str) -> None:
                Path(filename).write_text(
                    json.dumps({"states": self.states, "times": self.times, "metadata": self.metadata}),
                    encoding="utf-8",
                )

        monkeypatch.setattr(mod, "OUTPUT_DIR", output_dir)
        monkeypatch.setattr(mod.e2m2e.core, "CR3BP_System", lambda **_: object())
        monkeypatch.setattr(mod.e2m2e.core, "CR3BP_Dynamics", lambda **_: object())
        monkeypatch.setattr(mod, "_propagate_catalog_seed", lambda *a, **kw: FakeOrbit([[0, 0, 0, 0, 0, 0]], [0.0]))

        full_argv = list(cli_args) + ["--catalog-dir", str(catalog_dir)]
        mod.main(full_argv)

        saved = list(output_dir.glob("dro_catalog_*.json"))
        assert saved, "CLI run must produce a catalog output"
        payload = json.loads(saved[0].read_text(encoding="utf-8"))
        metadata = payload["metadata"]
        assert metadata["seed_source"] == "catalog_jacobi"
        assert metadata["matched_seed_id"] == "earth-moon_dro:000001"
        assert metadata["target_jacobi"] == 3.10005
        assert metadata["matched_jacobi"] == 3.1
        assert metadata["jacobi_delta"] == pytest.approx(0.00005)
        assert metadata["tolerance"] == 1e-3

    def test_gui_jacobi_strict_tolerance_failure_propagates(self, qapp_fixture, tmp_path):
        from tod.gui.script_tab_widget import ScriptTabWidget
        import tod.generates.cr3bp.dro.generate_dro_orbit as mod

        catalog_dir = tmp_path / "normalized"
        _write_dro_catalog(catalog_dir)

        widget = ScriptTabWidget(
            entry=_make_dro_entry(), files=[], repo_root=tmp_path,
            gui_defaults={}, theme_mode="system",
        )
        state = widget._catalog_seed_selectors["dro_catalog_seed"]
        state.enabled_checkbox.setChecked(True)
        state.mode_widget.setCurrentIndex(state.mode_widget.findData("jacobi_match"))
        state.jacobi_widget.setText("0.0")
        state.tolerance_widget.setText("0.1")

        cli_args = widget.collect_run_args()
        full_argv = list(cli_args) + ["--catalog-dir", str(catalog_dir)]

        with pytest.raises(SystemExit) as exc_info:
            mod.main(full_argv)

        message = str(exc_info.value)
        assert "Jacobi strict tolerance exceeded" in message
        assert "target=0.0" in message
        assert "tolerance=0.1" in message


class TestGuiSeedIdDrivesCliRegression:
    def test_gui_seed_id_args_drive_cli_with_filename_helper(self, qapp_fixture, tmp_path, monkeypatch):
        from tod.gui.script_tab_widget import ScriptTabWidget
        import tod.generates.cr3bp.dro.generate_dro_orbit as mod

        catalog_dir = tmp_path / "normalized"
        _write_dro_catalog(catalog_dir)
        output_dir = tmp_path / "out"

        widget = ScriptTabWidget(
            entry=_make_dro_entry(), files=[], repo_root=tmp_path,
            gui_defaults={}, theme_mode="system",
        )
        state = widget._catalog_seed_selectors["dro_catalog_seed"]
        cast(QComboBox, state.selector_widget).addItem(
            "earth-moon_dro:000001 | C=3.1 | T=7.0",
            "earth-moon_dro:000001",
        )
        state.enabled_checkbox.setChecked(True)
        cast(QComboBox, state.selector_widget).setCurrentIndex(1)

        cli_args = widget.collect_run_args()
        assert cli_args == ["--seed-id", "earth-moon_dro:000001"]

        class FakeOrbit:
            def __init__(self, states, times):
                self.states = states
                self.times = times
                self.period = None
                self.metadata: dict[str, object] = {}

            def save_to_file(self, filename: str) -> None:
                Path(filename).write_text(
                    json.dumps({"states": self.states, "times": self.times, "metadata": self.metadata}),
                    encoding="utf-8",
                )

        monkeypatch.setattr(mod, "OUTPUT_DIR", output_dir)
        monkeypatch.setattr(mod.time, "time", lambda: 1234567890)
        monkeypatch.setattr(mod.e2m2e.core, "CR3BP_System", lambda **_: object())
        monkeypatch.setattr(mod.e2m2e.core, "CR3BP_Dynamics", lambda **_: object())
        monkeypatch.setattr(mod, "_propagate_catalog_seed", lambda *a, **kw: FakeOrbit([[0, 0, 0, 0, 0, 0]], [0.0]))

        full_argv = list(cli_args) + ["--catalog-dir", str(catalog_dir)]
        mod.main(full_argv)

        saved = list(output_dir.glob("dro_catalog_*.json"))
        assert saved
        # Same filename helper as manual mode: dro_<ts>.json for manual,
        # dro_catalog_<safe_seed>_<ts>.json for catalog.
        assert saved[0].name.startswith("dro_catalog_earth-moon_dro_000001_")
        # Manual filename must never collide.
        manual_name = "dro_1234567890.json"
        assert not (output_dir / manual_name).exists()

        payload = json.loads(saved[0].read_text(encoding="utf-8"))
        metadata = payload["metadata"]
        assert metadata["seed_source"] == "catalog_seed_id"
        assert metadata["matched_seed_id"] == "earth-moon_dro:000001"
        assert metadata["raw_source_path"] == "earth-moon_dro.xlsx"
        assert metadata["normalized_catalog_dir"].endswith("normalized")


class TestCatalogOutputPlotCompatibility:
    def test_seed_id_and_jacobi_outputs_are_loaded_by_plot_consumer(self, tmp_path):
        # Both catalog output variants must be consumable by the plot
        # consumer (`FamilyPlotOrchestrator._load_orbit_data`).
        from tod.plot.family_plot_orchestrator import FamilyPlotOrchestrator, FamilyPlotConfig
        import argparse

        for selection_mode, seed_label in (("seed_id", "earth-moon_dro:000001"),
                                            ("jacobi", "earth-moon_dro:000001")):
            catalog_orbit = tmp_path / f"dro_catalog_{seed_label.replace(':', '_')}_123.json"
            catalog_orbit.write_text(
                json.dumps(
                    {
                        "states": [[1, 0, 0, 0, 1, 0], [1, 0.1, 0, -0.1, 1, 0]],
                        "times": [0, 1],
                        "properties": {"period": 1},
                        "metadata": {
                            "generation_method": "catalog_seed_propagation",
                            "selection_mode": selection_mode,
                            "matched_seed_id": seed_label,
                        },
                    }
                ),
                encoding="utf-8",
            )
            args = argparse.Namespace(json_file=str(catalog_orbit))
            orchestrator = FamilyPlotOrchestrator(
                FamilyPlotConfig(family_type="DRO", default_filename="dro",
                                 output_subdir="dro", plane="xy"),
                args,
            )
            family = orchestrator._load_orbit_data(catalog_orbit, system=None)
            assert len(family) == 1
