from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QComboBox, QLineEdit

from tod.gui.param_value_store import ParamValueStore
from tod.gui.script_param_panel import ScriptParamPanel
from tod.gui.script_registry import CatalogSeedSelectorParam, ScriptEntry


@pytest.fixture
def qapp_fixture():
    return QApplication.instance() or QApplication([])


def test_catalog_seed_selector_loads_seed_ids_only_when_enabled(qapp_fixture, tmp_path: Path) -> None:
    entry = ScriptEntry(
        module="dro",
        name="generate_dro_orbit",
        description="生成 DRO 轨道",
        script_path="tod/generates/cr3bp/dro/generate_dro_orbit.py",
        catalog_seed_selectors=[
            CatalogSeedSelectorParam(
                key="dro_catalog_seed",
                label="DRO Catalog 初值",
                orbit_type="dro",
                default_enabled=False,
            )
        ],
    )
    store = ParamValueStore(files=[], find_cli_param=lambda _: None)
    calls: list[tuple[Path, str]] = []

    def fake_loader(repo_root: Path, orbit_type: str):
        calls.append((repo_root, orbit_type))
        return [
            SimpleNamespace(orbit_id="earth-moon_dro:000001", jacobi=3.1, period=7.0),
            SimpleNamespace(orbit_id="earth-moon_dro:000002", jacobi=3.2, period=8.0),
        ]

    ScriptParamPanel(
        entry=entry,
        store=store,
        repo_root=tmp_path,
        gui_defaults={},
        theme_mode="light",
        catalog_seed_loader=fake_loader,
    )

    state = store._catalog_seed_selectors["dro_catalog_seed"]
    combo = state.selector_widget
    assert isinstance(combo, QComboBox)
    assert calls == []
    assert combo.count() == 1
    assert not state.enabled_checkbox.isChecked()

    state.enabled_checkbox.setChecked(True)

    assert calls == [(tmp_path, "dro")]
    assert combo.isEnabled()
    assert combo.count() == 2
    assert combo.itemData(0) == "earth-moon_dro:000001"
    assert combo.itemData(1) == "earth-moon_dro:000002"
    assert "C=3.1" in combo.itemText(0)
    assert "T=7" in combo.itemText(0)

    state.enabled_checkbox.setChecked(False)
    state.enabled_checkbox.setChecked(True)

    assert calls == [(tmp_path, "dro")]


def test_default_catalog_seed_loader_auto_builds_missing_normalized_catalog(qapp_fixture, tmp_path: Path, monkeypatch) -> None:
    entry = ScriptEntry(
        module="dro",
        name="generate_dro_orbit",
        description="生成 DRO 轨道",
        script_path="tod/generates/cr3bp/dro/generate_dro_orbit.py",
        catalog_seed_selectors=[CatalogSeedSelectorParam(key="dro_catalog_seed", label="DRO Catalog 初值", orbit_type="dro")],
    )
    store = ParamValueStore(files=[], find_cli_param=lambda _: None)
    calls: list[tuple[Path, Path, bool]] = []

    class FakeCatalog:
        def records(self, *, orbit_type=None):
            assert orbit_type == "dro"
            return [SimpleNamespace(orbit_id="earth-moon_dro:000001", jacobi=3.1, period=7.0)]

    def fake_import(raw_dir: Path, normalized_dir: Path, *, overwrite: bool = False):
        calls.append((raw_dir, normalized_dir, overwrite))
        normalized_dir.mkdir(parents=True)
        (normalized_dir / "index.csv").write_text("", encoding="utf-8")
        families_dir = normalized_dir / "families"
        families_dir.mkdir()
        (families_dir / "dro.csv").write_text("", encoding="utf-8")

    import tod.generates.cr3bp.importer as importer
    import tod.gui.script_param_panel as panel_mod
    monkeypatch.setattr(importer, "import_cr3bp_xlsx_catalog", fake_import)
    monkeypatch.setattr(importer, "load_cr3bp_catalog", lambda data_dir: FakeCatalog())
    monkeypatch.setattr(panel_mod, "import_cr3bp_xlsx_catalog", fake_import, raising=False)
    monkeypatch.setattr(panel_mod, "load_cr3bp_catalog", lambda data_dir: FakeCatalog(), raising=False)

    ScriptParamPanel(entry=entry, store=store, repo_root=tmp_path, gui_defaults={}, theme_mode="light")
    state = store._catalog_seed_selectors["dro_catalog_seed"]

    state.enabled_checkbox.setChecked(True)

    assert calls == [(
        tmp_path / "data" / "cr3bp_data" / "raw",
        tmp_path / "data" / "cr3bp_data" / "normalized",
        False,
    )]


def test_catalog_seed_selector_is_searchable_after_loading(qapp_fixture, tmp_path: Path) -> None:
    entry = ScriptEntry(
        module="dro",
        name="generate_dro_orbit",
        description="生成 DRO 轨道",
        script_path="tod/generates/cr3bp/dro/generate_dro_orbit.py",
        catalog_seed_selectors=[CatalogSeedSelectorParam(key="dro_catalog_seed", label="DRO Catalog 初值", orbit_type="dro")],
    )
    store = ParamValueStore(files=[], find_cli_param=lambda _: None)

    ScriptParamPanel(
        entry=entry,
        store=store,
        repo_root=tmp_path,
        gui_defaults={},
        theme_mode="light",
        catalog_seed_loader=lambda repo_root, orbit_type: [
            SimpleNamespace(orbit_id="earth-moon_dro:000001", jacobi=3.1, period=7.0),
        ],
    )
    state = store._catalog_seed_selectors["dro_catalog_seed"]

    state.enabled_checkbox.setChecked(True)

    combo = state.selector_widget
    assert isinstance(combo, QComboBox)
    assert combo.isEditable()
    assert combo.insertPolicy() == QComboBox.InsertPolicy.NoInsert
    assert combo.completer() is not None


def test_catalog_seed_selector_updates_lightweight_preview(qapp_fixture, tmp_path: Path) -> None:
    entry = ScriptEntry(
        module="dro",
        name="generate_dro_orbit",
        description="生成 DRO 轨道",
        script_path="tod/generates/cr3bp/dro/generate_dro_orbit.py",
        catalog_seed_selectors=[CatalogSeedSelectorParam(key="dro_catalog_seed", label="DRO Catalog 初值", orbit_type="dro")],
    )
    store = ParamValueStore(files=[], find_cli_param=lambda _: None)
    ScriptParamPanel(
        entry=entry,
        store=store,
        repo_root=tmp_path,
        gui_defaults={},
        theme_mode="light",
        catalog_seed_loader=lambda repo_root, orbit_type: [
            SimpleNamespace(
                orbit_id="earth-moon_dro:000001",
                jacobi=3.1,
                period=7.0,
                state=[1, 2, 3, 4, 5, 6],
                source_file="earth-moon_dro.xlsx",
                source_row=2,
            ),
            SimpleNamespace(
                orbit_id="earth-moon_dro:000002",
                jacobi=3.2,
                period=8.0,
                state=[6, 5, 4, 3, 2, 1],
                source_file="earth-moon_dro.xlsx",
                source_row=3,
            ),
        ],
    )
    state = store._catalog_seed_selectors["dro_catalog_seed"]

    state.enabled_checkbox.setChecked(True)
    state.selector_widget.setCurrentIndex(1)

    preview = state.preview_label.text()
    assert "earth-moon_dro:000002" in preview
    assert "C=3.2" in preview
    assert "T=8" in preview
    assert "[6, 5, 4, 3, 2, 1]" in preview
    assert "earth-moon_dro.xlsx" in preview


def test_catalog_seed_selector_supports_jacobi_mode_without_realtime_preview(qapp_fixture, tmp_path: Path) -> None:
    entry = ScriptEntry(
        module="dro",
        name="generate_dro_orbit",
        description="生成 DRO 轨道",
        script_path="tod/generates/cr3bp/dro/generate_dro_orbit.py",
        catalog_seed_selectors=[CatalogSeedSelectorParam(key="dro_catalog_seed", label="DRO Catalog 初值", orbit_type="dro")],
    )
    store = ParamValueStore(files=[], find_cli_param=lambda _: None)
    calls: list[str] = []

    ScriptParamPanel(
        entry=entry,
        store=store,
        repo_root=tmp_path,
        gui_defaults={},
        theme_mode="light",
        catalog_seed_loader=lambda repo_root, orbit_type: calls.append(orbit_type) or [
            SimpleNamespace(orbit_id="earth-moon_dro:000001", jacobi=3.1, period=7.0),
        ],
    )
    state = store._catalog_seed_selectors["dro_catalog_seed"]

    state.enabled_checkbox.setChecked(True)
    state.mode_widget.setCurrentIndex(state.mode_widget.findData("jacobi_match"))

    assert not state.selector_widget.isEnabled()
    assert state.jacobi_widget.isEnabled()
    assert state.tolerance_widget.isEnabled()
    assert isinstance(state.jacobi_widget, QLineEdit)
    assert isinstance(state.tolerance_widget, QLineEdit)

    state.jacobi_widget.setText("3.10005")
    state.tolerance_widget.setText("1e-4")

    assert calls == ["dro"]
