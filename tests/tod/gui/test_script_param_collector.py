"""ParamValueStore 参数收集 — 从控件字典收集 CLI 参数 / 环境变量 / 芯片选择 / 多文件配置的单元测试。"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from typing import Any
from unittest.mock import patch

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from tod.gui.params.param_value_store import ParamValueStore
from tod.scripting import CliChipParam, CliParam, ScriptEntry


def _make_entry(**overrides: Any) -> ScriptEntry:
    defaults: dict[str, Any] = dict(
        module="dro",
        name="Test Script",
        description="Test description",
        script_path="tod/generates/cr3bp/dro/generate_test.py",
    )
    defaults.update(overrides)
    return ScriptEntry(**defaults)


def _find_cli_param_factory(entry: ScriptEntry):
    def find_cli_param(key: str) -> CliParam | None:
        for p in entry.cli_params:
            if p.flag.lstrip("-").replace("-", "_") == key:
                return p
        return None

    return find_cli_param


def _make_store(
    entry: ScriptEntry,
    cli_widgets: dict[str, QWidget] | None = None,
    cli_row_containers: dict[str, QWidget] | None = None,
    param_defaults: dict[QWidget, str] | None = None,
    factory_defaults: dict[QWidget, str] | None = None,
    env_widgets: dict[str, QComboBox] | None = None,
    chip_widgets: dict[str, QWidget] | None = None,
    multi_file_widgets: dict[str, QWidget] | None = None,
) -> ParamValueStore:
    """构建一个填充了指定控件的 ParamValueStore。"""
    store = ParamValueStore(
        files=[],
        find_cli_param=_find_cli_param_factory(entry),
    )
    if cli_widgets:
        store._cli_widgets.update(cli_widgets)
    if cli_row_containers:
        store._row_containers.update(cli_row_containers)
    if param_defaults:
        store._param_defaults.update(param_defaults)
    if factory_defaults:
        store._factory_defaults.update(factory_defaults)
    if env_widgets:
        store._env_widgets.update(env_widgets)
    if chip_widgets:
        store._chip_widgets.update(chip_widgets)
    if multi_file_widgets:
        store._multi_file_widgets.update(multi_file_widgets)
    return store


@pytest.fixture
def qapp_fixture():
    app = QApplication.instance() or QApplication([])
    return app


# ── collect_run_args ─────────────────────────────────────────────


class TestCollectRunArgs:
    def test_checkbox_emits_flag_when_checked(self, qapp_fixture):
        entry = _make_entry(
            cli_params=[CliParam("--verbose", "详细", "bool")]
        )
        cb = QCheckBox()
        cb.setChecked(True)
        store = _make_store(entry, cli_widgets={"verbose": cb})
        assert store.collect_run_args(entry) == ["--verbose"]

    def test_checkbox_omits_flag_when_unchecked(self, qapp_fixture):
        entry = _make_entry(
            cli_params=[CliParam("--verbose", "详细", "bool")]
        )
        cb = QCheckBox()
        store = _make_store(entry, cli_widgets={"verbose": cb})
        assert "--verbose" not in store.collect_run_args(entry)

    def test_spinbox_omits_when_at_factory_default(self, qapp_fixture):
        entry = _make_entry(
            cli_params=[CliParam("--n", "n", "int", default="100")]
        )
        sp = QSpinBox()
        sp.setRange(-99999, 99999)
        sp.setValue(100)
        store = _make_store(entry, cli_widgets={"n": sp}, factory_defaults={sp: "100"})
        assert "--n" not in store.collect_run_args(entry)

    def test_spinbox_emits_when_changed(self, qapp_fixture):
        entry = _make_entry(
            cli_params=[CliParam("--n", "n", "int", default="100")]
        )
        sp = QSpinBox()
        sp.setRange(-99999, 99999)
        sp.setValue(200)
        store = _make_store(entry, cli_widgets={"n": sp}, factory_defaults={sp: "100"})
        assert store.collect_run_args(entry) == ["--n", "200"]

    def test_lineedit_omits_when_at_default(self, qapp_fixture):
        entry = _make_entry(
            cli_params=[CliParam("--orbit", "轨道", "str", default="halo")]
        )
        le = QLineEdit("halo")
        store = _make_store(entry, cli_widgets={"orbit": le}, param_defaults={le: "halo"})
        assert "--orbit" not in store.collect_run_args(entry)

    def test_lineedit_emits_when_changed(self, qapp_fixture):
        entry = _make_entry(
            cli_params=[CliParam("--orbit", "轨道", "str", default="halo")]
        )
        le = QLineEdit("dro")
        store = _make_store(entry, cli_widgets={"orbit": le}, param_defaults={le: "halo"})
        assert store.collect_run_args(entry) == ["--orbit", "dro"]

    def test_combobox_applies_choice_values_reverse_mapping(self, qapp_fixture):
        entry = _make_entry(
            cli_params=[
                CliParam("--halo-class", "族", "str", default="0",
                         choices=("北族", "南族"),
                         choice_values={"北族": "0", "南族": "1"}),
            ]
        )
        combo = QComboBox()
        combo.addItems(["北族", "南族"])
        combo.setCurrentText("南族")
        store = _make_store(entry, cli_widgets={"halo_class": combo}, param_defaults={combo: "北族"})
        assert store.collect_run_args(entry) == ["--halo-class", "1"]

    def test_hidden_container_widget_is_skipped(self, qapp_fixture):
        entry = _make_entry(
            cli_params=[
                CliParam("--a", "a", "str", default="x"),
                CliParam("--b", "b", "str", default="y"),
            ]
        )
        le_a = QLineEdit("modified_a")
        le_b = QLineEdit("modified_b")
        parent = QWidget()
        parent.show()
        container_a = QWidget(parent)
        container_a.setVisible(False)
        container_b = QWidget(parent)
        container_b.setVisible(True)
        store = _make_store(
            entry,
            cli_widgets={"a": le_a, "b": le_b},
            cli_row_containers={"a": container_a, "b": container_b},
            param_defaults={le_a: "x", le_b: "y"},
        )
        args = store.collect_run_args(entry)
        assert "--a" not in args
        assert args == ["--b", "modified_b"]


# ── collect_env_overrides ────────────────────────────────────────


class TestCollectEnvOverrides:
    def test_env_widgets_file_path_mapped(self, qapp_fixture):
        from tod.scripting import EnvParam

        entry = _make_entry(
            env_params={
                "dro_file": EnvParam("DRO_FILE", "DRO 文件", "dro", "json"),
            }
        )
        combo = QComboBox()
        combo.addItem("Display Text")
        combo.setItemData(0, "/abs/path/to/dro.json", Qt.ItemDataRole.UserRole)
        store = _make_store(entry, env_widgets={"dro_file": combo})
        assert store.collect_env_overrides(entry) == {"DRO_FILE": "/abs/path/to/dro.json"}

    def test_env_widgets_no_selection_omits(self, qapp_fixture):
        from tod.scripting import EnvParam

        entry = _make_entry(
            env_params={
                "dro_file": EnvParam("DRO_FILE", "DRO 文件", "dro", "json"),
            }
        )
        combo = QComboBox()
        store = _make_store(entry, env_widgets={"dro_file": combo})
        assert "DRO_FILE" not in store.collect_env_overrides(entry)

    def test_cli_file_category_widget_contributes_via_cli_to_env(self, qapp_fixture):
        entry = _make_entry(
            cli_params=[
                CliParam("--dro-file", "DRO 文件", "str",
                         file_category="dro"),
            ]
        )
        combo = QComboBox()
        combo.addItem("")
        combo.setItemData(0, "/abs/path/dro.json", Qt.ItemDataRole.UserRole)
        combo.setEditable(True)
        combo.setEditText("/abs/path/dro.json")
        store = _make_store(entry, cli_widgets={"dro_file": combo}, param_defaults={combo: ""})
        assert store.collect_env_overrides(entry).get("DRO_FILE") == "/abs/path/dro.json"


# ── collect_chip_selections ──────────────────────────────────────


class TestCollectChipSelections:
    def test_no_chips_returns_empty_dict(self, qapp_fixture):
        entry = _make_entry()
        container = QWidget()
        store = _make_store(entry, chip_widgets={"libration_point": container})
        assert store.collect_chip_selections(entry) == {}

    def test_chips_selected_returns_cli_values(self, qapp_fixture):
        entry = _make_entry(
            cli_chip_params=[
                CliChipParam(
                    "--libration-point", "平动点",
                    options={"L1": "L1", "L2": "L2"},
                    default="L1",
                )
            ]
        )
        container = QWidget()
        btn_l1 = QPushButton("L1")
        btn_l1.setProperty("_selected", True)
        btn_l2 = QPushButton("L2")
        btn_l2.setProperty("_selected", False)
        container._chip_buttons = {"L1": btn_l1, "L2": btn_l2}  # type: ignore[attr-defined]
        store = _make_store(entry, chip_widgets={"libration_point": container})
        assert store.collect_chip_selections(entry) == {"libration_point": ["L1"]}

    def test_multiple_chips_selected(self, qapp_fixture):
        entry = _make_entry(
            cli_chip_params=[
                CliChipParam(
                    "--libration-point", "平动点",
                    options={"L1": "L1", "L2": "L2", "L3": "L3"},
                )
            ]
        )
        container = QWidget()
        btn_l1 = QPushButton("L1")
        btn_l1.setProperty("_selected", True)
        btn_l2 = QPushButton("L2")
        btn_l2.setProperty("_selected", True)
        btn_l3 = QPushButton("L3")
        btn_l3.setProperty("_selected", False)
        container._chip_buttons = {"L1": btn_l1, "L2": btn_l2, "L3": btn_l3}  # type: ignore[attr-defined]
        store = _make_store(entry, chip_widgets={"libration_point": container})
        assert store.collect_chip_selections(entry) == {"libration_point": ["L1", "L2"]}


# ── collect_multi_file_configs ───────────────────────────────────


class TestCollectMultiFileConfigs:
    def test_empty_table_returns_empty(self, qapp_fixture):
        container = QWidget()
        table = QTableWidget(0, 2)
        table._per_file_fields = []  # type: ignore[attr-defined]
        from PyQt6.QtWidgets import QVBoxLayout
        container_layout = QWidget()
        v = QVBoxLayout(container_layout)
        v.addWidget(table)
        entry = _make_entry()
        store = _make_store(entry, multi_file_widgets={"json_file": container_layout})
        assert store.collect_multi_file_configs() == {}

    def test_row_with_spinbox_and_lineedit_cells(self, qapp_fixture):
        from tod.scripting import PerFileField

        table = QTableWidget(0, 4)
        per_fields = [
            PerFileField("start_idx", "起始", "int", default="-1"),
            PerFileField("end_value", "结束", "float", default="0.0"),
            PerFileField("step_label", "步长", "str", default=""),
        ]
        table._per_file_fields = per_fields  # type: ignore[attr-defined]

        table.insertRow(0)
        name_item = QTableWidgetItem("orbit.json")
        name_item.setData(Qt.ItemDataRole.UserRole, "/abs/orbit.json")
        table.setItem(0, 0, name_item)
        sp = QSpinBox()
        sp.setRange(-99999, 99999)
        sp.setValue(5)
        table.setCellWidget(0, 1, sp)
        le_float = QLineEdit("0.5")
        table.setCellWidget(0, 2, le_float)
        le_str = QLineEdit("note text")
        table.setCellWidget(0, 3, le_str)

        from PyQt6.QtWidgets import QVBoxLayout
        wrap = QWidget()
        QVBoxLayout(wrap).addWidget(table)

        entry = _make_entry()
        store = _make_store(entry, multi_file_widgets={"json_file": wrap})
        result = store.collect_multi_file_configs()
        assert "json_file" in result
        cfg = result["json_file"][0]
        assert cfg["path"] == "/abs/orbit.json"
        assert cfg["start_idx"] == 5
        assert cfg["end_value"] == 0.5
        assert cfg["step_label"] == "note text"


# ── validate_params ──────────────────────────────────────────────


class TestValidateParams:
    def test_required_file_missing_returns_false(self, qapp_fixture):
        entry = _make_entry(
            cli_params=[
                CliParam("--dro-file", "DRO 文件", "str",
                         file_category="dro", required=True),
            ]
        )
        combo = QComboBox()
        combo.setEditable(True)
        combo.setEditText("")
        store = _make_store(entry, cli_widgets={"dro_file": combo})
        parent = QWidget()
        with patch.object(QMessageBox, "warning", return_value=QMessageBox.StandardButton.Ok):
            result = store.validate_params(parent, entry)
        assert result is False

    def test_valid_float_returns_true(self, qapp_fixture):
        entry = _make_entry(
            cli_params=[
                CliParam("--tol", "容差", "float", default="1e-6"),
            ]
        )
        le = QLineEdit("1.5e-3")
        store = _make_store(entry, cli_widgets={"tol": le})
        parent = QWidget()
        assert store.validate_params(parent, entry) is True

    def test_invalid_float_returns_false(self, qapp_fixture):
        entry = _make_entry(
            cli_params=[
                CliParam("--tol", "容差", "float", default="1e-6"),
            ]
        )
        le = QLineEdit("not_a_number")
        store = _make_store(entry, cli_widgets={"tol": le})
        parent = QWidget()
        with patch.object(QMessageBox, "warning", return_value=QMessageBox.StandardButton.Ok):
            result = store.validate_params(parent, entry)
        assert result is False

    def test_hidden_container_skips_validation(self, qapp_fixture):
        entry = _make_entry(
            cli_params=[
                CliParam("--x", "x", "float", default="1.0",
                         hidden_when="--flag"),
            ]
        )
        le = QLineEdit("not_a_number")
        parent = QWidget()
        parent.show()
        container = QWidget(parent)
        container.setVisible(False)
        store = _make_store(entry, cli_widgets={"x": le}, cli_row_containers={"x": container})
        assert store.validate_params(parent, entry) is True
