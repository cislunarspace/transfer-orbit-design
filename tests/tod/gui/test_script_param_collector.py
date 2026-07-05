"""ScriptParamCollector — 从控件字典收集 CLI 参数 / 环境变量 / 芯片选择 / 多文件配置的单元测试。"""

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

from tod.gui.cli_widget_factory import CliWidgetFactory
from tod.gui.script_param_collector import ScriptParamCollector
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


@pytest.fixture
def qapp_fixture():
    app = QApplication.instance() or QApplication([])
    return app


def _build_factory(entry: ScriptEntry) -> CliWidgetFactory:
    """构建与 ParamValueStore 兼容的 widget_factory（共享 unit_combos 字典）。"""
    fac = CliWidgetFactory(files=[], on_path_mode_changed=lambda *a: None, on_unit_changed=lambda *a: None)
    for p in entry.cli_params:
        key, widget = fac.make_widget(p)
        # 关键：把 widget 注册到 _cli_widgets（虽然 collector 用的是 unit_combos 属性）
    return fac


# ── collect_run_args ─────────────────────────────────────────────


class TestCollectRunArgs:
    def test_checkbox_emits_flag_when_checked(self, qapp_fixture):
        entry = _make_entry(
            cli_params=[CliParam("--verbose", "详细", "bool")]
        )
        cb = QCheckBox()
        cb.setChecked(True)
        cli_widgets = {"verbose": cb}
        cli_row_containers: dict[str, QWidget] = {}
        args = ScriptParamCollector.collect_run_args(
            entry, cli_widgets, cli_row_containers,
            param_defaults={}, factory_defaults={},
            to_standard_unit=lambda le: le.text().strip(),
            unit_combos={}, find_cli_param=_find_cli_param_factory(entry),
        )
        assert args == ["--verbose"]

    def test_checkbox_omits_flag_when_unchecked(self, qapp_fixture):
        entry = _make_entry(
            cli_params=[CliParam("--verbose", "详细", "bool")]
        )
        cb = QCheckBox()
        cli_widgets = {"verbose": cb}
        args = ScriptParamCollector.collect_run_args(
            entry, cli_widgets, {},
            param_defaults={}, factory_defaults={},
            to_standard_unit=lambda le: le.text().strip(),
            unit_combos={}, find_cli_param=_find_cli_param_factory(entry),
        )
        assert "--verbose" not in args

    def test_spinbox_omits_when_at_factory_default(self, qapp_fixture):
        entry = _make_entry(
            cli_params=[CliParam("--n", "n", "int", default="100")]
        )
        sp = QSpinBox()
        sp.setRange(-99999, 99999)
        sp.setValue(100)
        cli_widgets = {"n": sp}
        args = ScriptParamCollector.collect_run_args(
            entry, cli_widgets, {},
            param_defaults={}, factory_defaults={sp: "100"},
            to_standard_unit=lambda le: le.text().strip(),
            unit_combos={}, find_cli_param=_find_cli_param_factory(entry),
        )
        assert "--n" not in args

    def test_spinbox_emits_when_changed(self, qapp_fixture):
        entry = _make_entry(
            cli_params=[CliParam("--n", "n", "int", default="100")]
        )
        sp = QSpinBox()
        sp.setRange(-99999, 99999)
        sp.setValue(200)
        cli_widgets = {"n": sp}
        args = ScriptParamCollector.collect_run_args(
            entry, cli_widgets, {},
            param_defaults={}, factory_defaults={sp: "100"},
            to_standard_unit=lambda le: le.text().strip(),
            unit_combos={}, find_cli_param=_find_cli_param_factory(entry),
        )
        assert args == ["--n", "200"]

    def test_lineedit_omits_when_at_default(self, qapp_fixture):
        entry = _make_entry(
            cli_params=[CliParam("--orbit", "轨道", "str", default="halo")]
        )
        le = QLineEdit("halo")
        cli_widgets = {"orbit": le}
        args = ScriptParamCollector.collect_run_args(
            entry, cli_widgets, {},
            param_defaults={le: "halo"}, factory_defaults={},
            to_standard_unit=lambda le: le.text().strip(),
            unit_combos={}, find_cli_param=_find_cli_param_factory(entry),
        )
        assert "--orbit" not in args

    def test_lineedit_emits_when_changed(self, qapp_fixture):
        entry = _make_entry(
            cli_params=[CliParam("--orbit", "轨道", "str", default="halo")]
        )
        le = QLineEdit("dro")
        cli_widgets = {"orbit": le}
        args = ScriptParamCollector.collect_run_args(
            entry, cli_widgets, {},
            param_defaults={le: "halo"}, factory_defaults={},
            to_standard_unit=lambda le: le.text().strip(),
            unit_combos={}, find_cli_param=_find_cli_param_factory(entry),
        )
        assert args == ["--orbit", "dro"]

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
        cli_widgets = {"halo_class": combo}
        args = ScriptParamCollector.collect_run_args(
            entry, cli_widgets, {},
            param_defaults={combo: "北族"}, factory_defaults={},
            to_standard_unit=lambda le: le.text().strip(),
            unit_combos={}, find_cli_param=_find_cli_param_factory(entry),
        )
        # "南族" → reverse 映射为 "1"
        assert args == ["--halo-class", "1"]

    def test_hidden_container_widget_is_skipped(self, qapp_fixture):
        entry = _make_entry(
            cli_params=[
                CliParam("--a", "a", "str", default="x"),
                CliParam("--b", "b", "str", default="y"),
            ]
        )
        le_a = QLineEdit("modified_a")
        le_b = QLineEdit("modified_b")
        # 容器需要父 widget 并显式 setVisible(True) 才会处于非隐藏状态
        parent = QWidget()
        parent.show()
        container_a = QWidget(parent)
        container_a.setVisible(False)  # hidden
        container_b = QWidget(parent)
        container_b.setVisible(True)   # visible
        cli_widgets = {"a": le_a, "b": le_b}
        cli_row_containers = {"a": container_a, "b": container_b}
        args = ScriptParamCollector.collect_run_args(
            entry, cli_widgets, cli_row_containers,
            param_defaults={le_a: "x", le_b: "y"}, factory_defaults={},
            to_standard_unit=lambda le: le.text().strip(),
            unit_combos={}, find_cli_param=_find_cli_param_factory(entry),
        )
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
        env_widgets = {"dro_file": combo}
        overrides = ScriptParamCollector.collect_env_overrides(
            entry, env_widgets, cli_widgets={},
            param_defaults={}, find_cli_param=_find_cli_param_factory(entry),
        )
        assert overrides == {"DRO_FILE": "/abs/path/to/dro.json"}

    def test_env_widgets_no_selection_omits(self, qapp_fixture):
        from tod.scripting import EnvParam

        entry = _make_entry(
            env_params={
                "dro_file": EnvParam("DRO_FILE", "DRO 文件", "dro", "json"),
            }
        )
        combo = QComboBox()
        env_widgets = {"dro_file": combo}
        overrides = ScriptParamCollector.collect_env_overrides(
            entry, env_widgets, cli_widgets={},
            param_defaults={}, find_cli_param=_find_cli_param_factory(entry),
        )
        assert "DRO_FILE" not in overrides

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
        # 模拟在 file_category 模式下，currentText 填的是绝对路径
        combo.setEditable(True)
        combo.setEditText("/abs/path/dro.json")
        cli_widgets = {"dro_file": combo}
        overrides = ScriptParamCollector.collect_env_overrides(
            entry, env_widgets={}, cli_widgets=cli_widgets,
            param_defaults={combo: ""}, find_cli_param=_find_cli_param_factory(entry),
        )
        assert overrides.get("DRO_FILE") == "/abs/path/dro.json"


# ── collect_chip_selections ──────────────────────────────────────


class TestCollectChipSelections:
    def test_no_chips_returns_empty_dict(self, qapp_fixture):
        entry = _make_entry()
        # 一个容器但没有 _chip_buttons 属性
        container = QWidget()
        result = ScriptParamCollector.collect_chip_selections(
            entry, {"libration_point": container},
        )
        assert result == {}

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
        # 模拟两个 chip 按钮：L1 选中，L2 未选
        btn_l1 = QPushButton("L1")
        btn_l1.setProperty("_selected", True)
        btn_l2 = QPushButton("L2")
        btn_l2.setProperty("_selected", False)
        container._chip_buttons = {"L1": btn_l1, "L2": btn_l2}  # type: ignore[attr-defined]

        result = ScriptParamCollector.collect_chip_selections(
            entry, {"libration_point": container},
        )
        assert result == {"libration_point": ["L1"]}

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

        result = ScriptParamCollector.collect_chip_selections(
            entry, {"libration_point": container},
        )
        assert result == {"libration_point": ["L1", "L2"]}


# ── collect_multi_file_configs ───────────────────────────────────


class TestCollectMultiFileConfigs:
    def test_empty_table_returns_empty(self, qapp_fixture):
        container = QWidget()
        table = QTableWidget(0, 2)
        table._per_file_fields = []  # type: ignore[attr-defined]
        container_layout = container
        # 注入 findChild 可见的子节点
        from PyQt6.QtWidgets import QVBoxLayout
        container_layout = QWidget()
        v = QVBoxLayout(container_layout)
        v.addWidget(table)
        result = ScriptParamCollector.collect_multi_file_configs(
            {"json_file": container_layout},
        )
        assert result == {}

    def test_row_with_spinbox_and_lineedit_cells(self, qapp_fixture):
        from tod.scripting import PerFileField

        table = QTableWidget(0, 4)
        per_fields = [
            PerFileField("start_idx", "起始", "int", default="-1"),
            PerFileField("end_value", "结束", "float", default="0.0"),
            PerFileField("step_label", "步长", "str", default=""),
        ]
        table._per_file_fields = per_fields  # type: ignore[attr-defined]

        # 插入一行
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

        result = ScriptParamCollector.collect_multi_file_configs(
            {"json_file": wrap},
        )
        assert "json_file" in result
        cfg = result["json_file"][0]
        assert cfg["path"] == "/abs/orbit.json"
        # QSpinBox value 通过 .value() 取
        assert cfg["start_idx"] == 5
        # float 字段被解析为 float
        assert cfg["end_value"] == 0.5
        # str 字段直接传文本
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
        combo.setEditText("")  # 空
        cli_widgets = {"dro_file": combo}
        cli_row_containers: dict[str, QWidget] = {}

        parent = QWidget()
        with patch.object(QMessageBox, "warning", return_value=QMessageBox.StandardButton.Ok):
            result = ScriptParamCollector.validate_params(
                parent, entry, cli_widgets, cli_row_containers,
                find_cli_param=_find_cli_param_factory(entry),
            )
        assert result is False

    def test_valid_float_returns_true(self, qapp_fixture):
        entry = _make_entry(
            cli_params=[
                CliParam("--tol", "容差", "float", default="1e-6"),
            ]
        )
        le = QLineEdit("1.5e-3")
        cli_widgets = {"tol": le}
        cli_row_containers: dict[str, QWidget] = {}
        parent = QWidget()
        result = ScriptParamCollector.validate_params(
            parent, entry, cli_widgets, cli_row_containers,
            find_cli_param=_find_cli_param_factory(entry),
        )
        assert result is True

    def test_invalid_float_returns_false(self, qapp_fixture):
        entry = _make_entry(
            cli_params=[
                CliParam("--tol", "容差", "float", default="1e-6"),
            ]
        )
        le = QLineEdit("not_a_number")
        cli_widgets = {"tol": le}
        cli_row_containers: dict[str, QWidget] = {}
        parent = QWidget()
        with patch.object(QMessageBox, "warning", return_value=QMessageBox.StandardButton.Ok):
            result = ScriptParamCollector.validate_params(
                parent, entry, cli_widgets, cli_row_containers,
                find_cli_param=_find_cli_param_factory(entry),
            )
        assert result is False

    def test_hidden_container_skips_validation(self, qapp_fixture):
        entry = _make_entry(
            cli_params=[
                CliParam("--x", "x", "float", default="1.0",
                         hidden_when="--flag"),
            ]
        )
        le = QLineEdit("not_a_number")  # 即使无效也应跳过
        parent = QWidget()
        parent.show()
        container = QWidget(parent)
        container.setVisible(False)
        cli_widgets = {"x": le}
        cli_row_containers = {"x": container}
        result = ScriptParamCollector.validate_params(
            parent, entry, cli_widgets, cli_row_containers,
            find_cli_param=_find_cli_param_factory(entry),
        )
        assert result is True
