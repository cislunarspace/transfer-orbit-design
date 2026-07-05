"""ParamValueStore — 单位换算 / 控件值写入 / 默认值持久化 / 条件可见性的单元测试。"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from typing import Any

import pytest
from PyQt6.QtWidgets import QApplication, QCheckBox, QComboBox, QLineEdit, QSpinBox, QWidget

from tod.gui.param_value_store import ParamValueStore
from tod.scripting import CliParam, ScriptEntry


def _make_entry(**overrides: Any) -> ScriptEntry:
    defaults: dict[str, Any] = dict(
        module="dro",
        name="Test Script",
        description="Test description",
        script_path="tod/generates/cr3bp/dro/generate_test.py",
    )
    defaults.update(overrides)
    return ScriptEntry(**defaults)


@pytest.fixture
def qapp_fixture():
    app = QApplication.instance() or QApplication([])
    return app


def _make_store(entry: ScriptEntry) -> ParamValueStore:
    def find_cli_param(key: str) -> CliParam | None:
        for p in entry.cli_params:
            if p.flag.lstrip("-").replace("-", "_") == key:
                return p
        return None

    return ParamValueStore(files=[], find_cli_param=find_cli_param)


# ── to_standard_unit ─────────────────────────────────────────────


class TestToStandardUnit:
    def test_empty_string_passes_through(self, qapp_fixture):
        store = _make_store(_make_entry())
        le = QLineEdit("")
        assert store.to_standard_unit(le) == ""

    def test_non_numeric_passes_through(self, qapp_fixture):
        # 没有 unit_group 时直接返回原文
        store = _make_store(_make_entry())
        le = QLineEdit("not_a_number")
        assert store.to_standard_unit(le) == "not_a_number"

    def test_valid_number_converts_via_factor(self, qapp_fixture):
        entry = _make_entry(
            cli_params=[
                CliParam("--length", "长度", "float", default="1.0",
                         unit_group="distance", default_unit="km"),
            ]
        )
        store = _make_store(entry)
        # make_widget 注册了 unit_groups / unit_combos 映射。
        # default 1.0 (DU) 在 km 单位下显示为 384405.0。
        _, le = store.widget_factory.make_widget(entry.cli_params[0])
        assert le.text() != ""  # 已设置显示值
        # to_standard_unit 应把显示值换算回标准单位 1.0
        result = store.to_standard_unit(le)
        assert float(result) == pytest.approx(1.0, rel=1e-6)

    def test_non_numeric_with_unit_group_passes_through(self, qapp_fixture):
        entry = _make_entry(
            cli_params=[
                CliParam("--length", "长度", "float", default="1.0",
                         unit_group="distance", default_unit="km"),
            ]
        )
        store = _make_store(entry)
        _, le = store.widget_factory.make_widget(entry.cli_params[0])
        le.setText("abc")
        assert store.to_standard_unit(le) == "abc"

    def test_default_unit_converts_correctly(self, qapp_fixture):
        """DU 单位下，显示值即标准值。"""
        entry = _make_entry(
            cli_params=[
                CliParam("--length", "长度", "float", default="100.0",
                         unit_group="distance", default_unit="DU"),
            ]
        )
        store = _make_store(entry)
        _, le = store.widget_factory.make_widget(entry.cli_params[0])
        result = store.to_standard_unit(le)
        assert float(result) == pytest.approx(100.0, rel=1e-9)


# ── set_widget_std_value ─────────────────────────────────────────


class TestSetWidgetStdValue:
    def test_checkbox_parses_true(self, qapp_fixture):
        store = _make_store(_make_entry())
        cb = QCheckBox()
        store.set_widget_std_value(cb, "True")
        assert cb.isChecked()

    def test_checkbox_parses_false(self, qapp_fixture):
        store = _make_store(_make_entry())
        cb = QCheckBox()
        cb.setChecked(True)
        store.set_widget_std_value(cb, "False")
        assert not cb.isChecked()

    def test_spinbox_parses_int(self, qapp_fixture):
        store = _make_store(_make_entry())
        sp = QSpinBox()
        store.set_widget_std_value(sp, "42")
        assert sp.value() == 42

    def test_spinbox_parses_float_string(self, qapp_fixture):
        store = _make_store(_make_entry())
        sp = QSpinBox()
        store.set_widget_std_value(sp, "7.0")
        assert sp.value() == 7

    def test_lineedit_sets_text(self, qapp_fixture):
        store = _make_store(_make_entry())
        le = QLineEdit()
        store.set_widget_std_value(le, "hello")
        assert le.text() == "hello"

    def test_combobox_reverse_maps_choice_values(self, qapp_fixture):
        entry = _make_entry(
            cli_params=[
                CliParam("--halo-class", "Class", "str", default="0",
                         choices=("北族", "南族"),
                         choice_values={"北族": "0", "南族": "1"}),
            ]
        )
        store = _make_store(entry)
        combo = QComboBox()
        combo.addItems(["北族", "南族"])
        # 把 widget 注册到 store，使 reverse map 生效
        store._cli_widgets["halo_class"] = combo
        # std 是 "0" → 应当 reverse 映射到 "北族"
        store.set_widget_std_value(combo, "0")
        assert combo.currentText() == "北族"

    def test_combobox_no_choice_values_sets_text_directly(self, qapp_fixture):
        entry = _make_entry(
            cli_params=[
                CliParam("--orbit", "轨道", "str", default="halo",
                         choices=("halo", "dro")),
            ]
        )
        store = _make_store(entry)
        combo = QComboBox()
        combo.addItems(["halo", "dro"])
        store._cli_widgets["orbit"] = combo
        store.set_widget_std_value(combo, "dro")
        assert combo.currentText() == "dro"


# ── save_defaults / reset_defaults ───────────────────────────────


class TestSaveAndResetDefaults:
    def test_save_defaults_records_modifications(self, qapp_fixture):
        entry = _make_entry(
            cli_params=[
                CliParam("--orbit", "轨道", "str", default="halo"),
            ]
        )
        store = _make_store(entry)
        le = QLineEdit()
        store._cli_widgets["orbit"] = le
        le.setText("dro")

        gui_defaults: dict[str, Any] = {}
        store.save_defaults(entry, gui_defaults)
        assert gui_defaults["Test Script"]["--orbit"] == "dro"

    def test_round_trip_via_save_then_reset(self, qapp_fixture):
        entry = _make_entry(
            cli_params=[
                CliParam("--orbit", "轨道", "str", default="halo"),
            ]
        )
        store = _make_store(entry)
        le = QLineEdit()
        store._cli_widgets["orbit"] = le
        le.setText("dro")

        gui_defaults: dict[str, Any] = {}
        store.save_defaults(entry, gui_defaults)
        # widget 的 _param_defaults 现在记录为 "dro"
        assert store._param_defaults[le] == "dro"

        # reset → 还原为 factory default "halo"
        store.reset_defaults(entry, gui_defaults)
        assert "Test Script" not in gui_defaults
        assert le.text() == "halo"
        assert store._param_defaults[le] == "halo"

    def test_reset_restores_factory_choices_via_reverse(self, qapp_fixture):
        entry = _make_entry(
            cli_params=[
                CliParam("--halo-class", "Class", "str", default="0",
                         choices=("北族", "南族"),
                         choice_values={"北族": "0", "南族": "1"}),
            ]
        )
        store = _make_store(entry)
        combo = QComboBox()
        combo.addItems(["北族", "南族"])
        store._cli_widgets["halo_class"] = combo
        combo.setCurrentText("南族")

        gui_defaults: dict[str, Any] = {}
        store.reset_defaults(entry, gui_defaults)
        # factory default 是 "0" → reverse 映射回 "北族"
        assert combo.currentText() == "北族"

    def test_save_records_checkbox_state(self, qapp_fixture):
        entry = _make_entry(
            cli_params=[
                CliParam("--verbose", "详细", "bool"),
            ]
        )
        store = _make_store(entry)
        cb = QCheckBox()
        store._cli_widgets["verbose"] = cb
        cb.setChecked(True)

        gui_defaults: dict[str, Any] = {}
        store.save_defaults(entry, gui_defaults)
        assert gui_defaults["Test Script"]["--verbose"] == "True"

    def test_save_records_spinbox_value(self, qapp_fixture):
        entry = _make_entry(
            cli_params=[
                CliParam("--iter", "迭代", "int", default="10"),
            ]
        )
        store = _make_store(entry)
        sp = QSpinBox()
        store._cli_widgets["iter"] = sp
        sp.setValue(99)

        gui_defaults: dict[str, Any] = {}
        store.save_defaults(entry, gui_defaults)
        assert gui_defaults["Test Script"]["--iter"] == "99"


# ── update_param_highlight ───────────────────────────────────────


class TestUpdateParamHighlight:
    def _setup_with_lineedit(self, default_text: str) -> tuple[ParamValueStore, QLineEdit]:
        entry = _make_entry(
            cli_params=[
                CliParam("--name", "名称", "str", default=default_text),
            ]
        )
        store = _make_store(entry)
        le = QLineEdit(default_text)
        store._cli_widgets["name"] = le
        store._param_defaults[le] = default_text
        return store, le

    def test_applies_modified_border_when_changed(self, qapp_fixture):
        store, le = self._setup_with_lineedit("halo")
        le.setText("dro")
        store.update_param_highlight(le)
        assert "border" in le.styleSheet()

    def test_removes_modified_border_when_at_default(self, qapp_fixture):
        store, le = self._setup_with_lineedit("halo")
        le.setText("dro")
        store.update_param_highlight(le)
        assert "border" in le.styleSheet()
        le.setText("halo")
        store.update_param_highlight(le)
        assert "border" not in le.styleSheet()

    def test_applies_on_spinbox_when_changed(self, qapp_fixture):
        entry = _make_entry(
            cli_params=[
                CliParam("--n", "n", "int", default="10"),
            ]
        )
        store = _make_store(entry)
        sp = QSpinBox()
        sp.setValue(10)
        store._cli_widgets["n"] = sp
        store._param_defaults[sp] = "10"
        sp.setValue(99)
        store.update_param_highlight(sp)
        assert "border" in sp.styleSheet()

    def test_removes_on_spinbox_when_at_default(self, qapp_fixture):
        entry = _make_entry(
            cli_params=[
                CliParam("--n", "n", "int", default="10"),
            ]
        )
        store = _make_store(entry)
        sp = QSpinBox()
        sp.setValue(99)
        store._cli_widgets["n"] = sp
        store._param_defaults[sp] = "10"
        store.update_param_highlight(sp)
        assert "border" in sp.styleSheet()
        sp.setValue(10)
        store.update_param_highlight(sp)
        assert "border" not in sp.styleSheet()


# ── setup_conditional_visibility (smoke) ─────────────────────────


class TestSetupConditionalVisibility:
    def test_checkbox_trigger_hides_target_when_checked(self, qapp_fixture):
        entry = _make_entry(
            cli_params=[
                CliParam("--verbose", "详细", "bool"),
                CliParam("--extra", "额外", "str", hidden_when="--verbose"),
            ]
        )
        store = _make_store(entry)

        trigger = QCheckBox()
        trigger.setChecked(True)
        target_container = QWidget()
        target_container.setVisible(True)
        target_label = QWidget()
        target_label.setVisible(True)

        store._cli_widgets = {
            "verbose": trigger,
            "extra": QWidget(),
        }
        store._row_containers = {"extra": target_container}
        store._row_labels = {"extra": target_label}

        store.setup_conditional_visibility(entry)

        assert not target_container.isVisible()
        assert not target_label.isVisible()

    def test_checkbox_trigger_shows_target_when_unchecked(self, qapp_fixture):
        entry = _make_entry(
            cli_params=[
                CliParam("--verbose", "详细", "bool"),
                CliParam("--extra", "额外", "str", hidden_when="--verbose"),
            ]
        )
        store = _make_store(entry)

        trigger = QCheckBox()
        trigger.setChecked(False)
        target_container = QWidget()
        target_container.setVisible(True)

        store._cli_widgets = {
            "verbose": trigger,
            "extra": QWidget(),
        }
        store._row_containers = {"extra": target_container}
        store._row_labels = {}

        store.setup_conditional_visibility(entry)

        assert target_container.isVisible()

    def test_checkbox_signal_toggles_visibility(self, qapp_fixture):
        entry = _make_entry(
            cli_params=[
                CliParam("--verbose", "详细", "bool"),
                CliParam("--extra", "额外", "str", hidden_when="--verbose"),
            ]
        )
        store = _make_store(entry)

        trigger = QCheckBox()
        trigger.setChecked(True)
        target_container = QWidget()
        target_container.setVisible(True)

        store._cli_widgets = {
            "verbose": trigger,
            "extra": QWidget(),
        }
        store._row_containers = {"extra": target_container}
        store._row_labels = {}

        store.setup_conditional_visibility(entry)
        assert not target_container.isVisible()

        trigger.setChecked(False)
        assert target_container.isVisible()

        trigger.setChecked(True)
        assert not target_container.isVisible()
