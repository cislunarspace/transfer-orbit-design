"""UnitStore / VisibilityStore / ParamStore — 各子 store 的独立单元测试。"""

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from typing import Any
from unittest.mock import patch

import pytest
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QLineEdit,
    QMessageBox, QSpinBox, QWidget,
)

from tod.gui.params.cli_widget_factory import CliWidgetFactory
from tod.gui.params.param_value_store import (
    ParamStore, ParamValueStore, UnitStore, VisibilityStore,
)
from tod.scripting import CliParam, ScriptEntry


def _make_entry(**overrides: Any) -> ScriptEntry:
    defaults: dict[str, Any] = dict(
        module="dro", name="Test Script", description="Test",
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


def _noop_mode_changed(a, b): pass
def _noop_unit_changed(a, b, c): pass


# ── UnitStore 独立测试 ──────────────────────────────────────────


class TestUnitStoreIndependent:
    def _make_unit_store(self, entry: ScriptEntry):
        factory = CliWidgetFactory(files=[], on_path_mode_changed=_noop_mode_changed, on_unit_changed=_noop_unit_changed)
        store = UnitStore(widget_factory=factory)
        for p in entry.cli_params:
            if p.unit_group:
                factory.make_widget(p)
        return store, factory

    def test_empty_text_returns_empty(self, qapp_fixture):
        store, _ = self._make_unit_store(_make_entry())
        assert store.to_standard_unit(QLineEdit("")) == ""

    def test_no_unit_group_returns_raw_text(self, qapp_fixture):
        store, _ = self._make_unit_store(_make_entry())
        assert store.to_standard_unit(QLineEdit("abc")) == "abc"

    def test_valid_number_converts(self, qapp_fixture):
        entry = _make_entry(cli_params=[
            CliParam("--length", "长度", "float", default="1.0", unit_group="distance", default_unit="km"),
        ])
        store, factory = self._make_unit_store(entry)
        le = list(factory.unit_groups.keys())[0]
        assert float(store.to_standard_unit(le)) == pytest.approx(1.0, rel=1e-6)


# ── VisibilityStore 独立测试 ────────────────────────────────────


class TestVisibilityStoreIndependent:
    def _make_stores(self, entry: ScriptEntry):
        cli_widgets: dict[str, QWidget] = {}
        find = _find_cli_param_factory(entry)
        factory = CliWidgetFactory(files=[], on_path_mode_changed=_noop_mode_changed, on_unit_changed=_noop_unit_changed)
        unit_store = UnitStore(widget_factory=factory)
        vis = VisibilityStore(find_cli_param=find, cli_widgets=cli_widgets, unit_store=unit_store, widget_factory=factory)
        return vis, cli_widgets

    def test_checkbox_hides_target(self, qapp_fixture):
        entry = _make_entry(cli_params=[
            CliParam("--verbose", "详细", "bool"),
            CliParam("--extra", "额外", "str", hidden_when="--verbose"),
        ])
        vis, cli_widgets = self._make_stores(entry)
        trigger = QCheckBox()
        trigger.setChecked(True)
        cli_widgets["verbose"] = trigger
        cli_widgets["extra"] = QWidget()
        target_container = QWidget()
        target_container.setVisible(True)
        target_label = QWidget()
        target_label.setVisible(True)
        vis._row_containers["extra"] = target_container
        vis._row_labels["extra"] = target_label
        vis.setup_conditional_visibility(entry)
        assert not target_container.isVisible()
        assert not target_label.isVisible()

    def test_checkbox_shows_target_when_unchecked(self, qapp_fixture):
        entry = _make_entry(cli_params=[
            CliParam("--verbose", "详细", "bool"),
            CliParam("--extra", "额外", "str", hidden_when="--verbose"),
        ])
        vis, cli_widgets = self._make_stores(entry)
        trigger = QCheckBox()
        trigger.setChecked(False)
        cli_widgets["verbose"] = trigger
        cli_widgets["extra"] = QWidget()
        target = QWidget()
        target.setVisible(True)
        vis._row_containers["extra"] = target
        vis.setup_conditional_visibility(entry)
        assert target.isVisible()

    def test_signal_toggles_visibility(self, qapp_fixture):
        entry = _make_entry(cli_params=[
            CliParam("--verbose", "详细", "bool"),
            CliParam("--extra", "额外", "str", hidden_when="--verbose"),
        ])
        vis, cli_widgets = self._make_stores(entry)
        trigger = QCheckBox()
        trigger.setChecked(True)
        cli_widgets["verbose"] = trigger
        cli_widgets["extra"] = QWidget()
        target = QWidget()
        target.setVisible(True)
        vis._row_containers["extra"] = target
        vis.setup_conditional_visibility(entry)
        assert not target.isVisible()
        trigger.setChecked(False)
        assert target.isVisible()
        trigger.setChecked(True)
        assert not target.isVisible()

    def test_highlight_applies_border(self, qapp_fixture):
        entry = _make_entry(cli_params=[CliParam("--name", "名称", "str", default="halo")])
        vis, _ = self._make_stores(entry)
        le = QLineEdit("halo")
        vis._param_defaults[le] = "halo"
        vis.connect_param_highlight(le)
        le.setText("dro")
        assert "border" in le.styleSheet()

    def test_highlight_removes_border_at_default(self, qapp_fixture):
        entry = _make_entry(cli_params=[CliParam("--name", "名称", "str", default="halo")])
        vis, _ = self._make_stores(entry)
        le = QLineEdit("halo")
        vis._param_defaults[le] = "halo"
        le.setText("dro")
        vis._update_param_highlight(le)
        assert "border" in le.styleSheet()
        le.setText("halo")
        vis._update_param_highlight(le)
        assert "border" not in le.styleSheet()


# ── VisibilityStore 公共接口独立测试（issue #328 验收点） ───────


class TestVisibilityStorePublicApi:
    """覆盖 get/set_param_default / is_row_hidden / clear_defaults / clear_visibility。"""

    def _make_store(self, entry: ScriptEntry | None = None):
        cli_widgets: dict[str, QWidget] = {}
        find = _find_cli_param_factory(entry or _make_entry())
        factory = CliWidgetFactory(
            files=[],
            on_path_mode_changed=_noop_mode_changed,
            on_unit_changed=_noop_unit_changed,
        )
        unit_store = UnitStore(widget_factory=factory)
        vis = VisibilityStore(
            find_cli_param=find,
            cli_widgets=cli_widgets,
            unit_store=unit_store,
            widget_factory=factory,
        )
        return vis

    def test_get_param_default_returns_empty_for_unknown(self, qapp_fixture):
        vis = self._make_store()
        assert vis.get_param_default(QLineEdit()) == ""

    def test_set_param_default_writes_and_refreshes_highlight(self, qapp_fixture):
        vis = self._make_store()
        le = QLineEdit("dro")
        # 默认值与当前不一致 → 高亮生效
        vis.set_param_default(le, "halo")
        assert vis.get_param_default(le) == "halo"
        assert "border" in le.styleSheet()

    def test_set_param_default_to_current_removes_border(self, qapp_fixture):
        vis = self._make_store()
        le = QLineEdit("halo")
        vis.set_param_default(le, "halo")
        assert vis.get_param_default(le) == "halo"
        assert "border" not in le.styleSheet()

    def test_is_row_hidden_false_when_key_absent(self, qapp_fixture):
        vis = self._make_store()
        assert vis.is_row_hidden("nonexistent_key") is False

    def test_is_row_hidden_reflects_container_visibility(self, qapp_fixture):
        vis = self._make_store()
        container = QWidget()
        container.setVisible(False)
        vis._row_containers["a"] = container
        assert vis.is_row_hidden("a") is True
        container.setVisible(True)
        assert vis.is_row_hidden("a") is False

    def test_clear_defaults_empties_param_defaults(self, qapp_fixture):
        vis = self._make_store()
        le = QLineEdit("x")
        vis.set_param_default(le, "default")
        assert len(vis._param_defaults) == 1
        vis.clear_defaults()
        assert len(vis._param_defaults) == 0

    def test_clear_visibility_empties_row_dicts(self, qapp_fixture):
        vis = self._make_store()
        vis._row_containers["a"] = QWidget()
        vis._row_labels["a"] = QWidget()
        vis.clear_visibility()
        assert len(vis._row_containers) == 0
        assert len(vis._row_labels) == 0

    def test_clear_visibility_does_not_touch_param_defaults(self, qapp_fixture):
        """clear_visibility 与 clear_defaults 职责正交。"""
        vis = self._make_store()
        le = QLineEdit("x")
        vis.set_param_default(le, "d")
        vis._row_containers["a"] = QWidget()
        vis.clear_visibility()
        assert vis.get_param_default(le) == "d"
        assert len(vis._row_containers) == 0


# ── ParamStore 独立测试 ─────────────────────────────────────────


class TestParamStoreIndependent:
    def _make_param_store(self, entry: ScriptEntry) -> ParamStore:
        find = _find_cli_param_factory(entry)
        factory = CliWidgetFactory(files=[], on_path_mode_changed=_noop_mode_changed, on_unit_changed=_noop_unit_changed)
        unit_store = UnitStore(widget_factory=factory)
        # 共享 cli_widgets dict：两个 store 引用同一个 dict，构造顺序无关（issue #329 方案 B）。
        shared_cli_widgets: dict[str, QWidget] = {}
        vis = VisibilityStore(
            find_cli_param=find,
            cli_widgets=shared_cli_widgets,
            unit_store=unit_store,
            widget_factory=factory,
        )
        param_store = ParamStore(
            files=[],
            find_cli_param=find,
            unit_store=unit_store,
            visibility_store=vis,
            widget_factory=factory,
            cli_widgets=shared_cli_widgets,
        )
        return param_store

    def test_set_widget_std_value_checkbox(self, qapp_fixture):
        store = self._make_param_store(_make_entry())
        cb = QCheckBox()
        store.set_widget_std_value(cb, "True")
        assert cb.isChecked()

    def test_set_widget_std_value_spinbox(self, qapp_fixture):
        store = self._make_param_store(_make_entry())
        sp = QSpinBox()
        store.set_widget_std_value(sp, "42")
        assert sp.value() == 42

    def test_set_widget_std_value_lineedit(self, qapp_fixture):
        store = self._make_param_store(_make_entry())
        le = QLineEdit()
        store.set_widget_std_value(le, "hello")
        assert le.text() == "hello"

    def test_save_defaults_records_value(self, qapp_fixture):
        entry = _make_entry(cli_params=[CliParam("--orbit", "轨道", "str", default="halo")])
        store = self._make_param_store(entry)
        le = QLineEdit()
        store._cli_widgets["orbit"] = le
        le.setText("dro")
        gui_defaults: dict[str, Any] = {}
        store.save_defaults(entry, gui_defaults)
        assert gui_defaults["Test Script"]["--orbit"] == "dro"

    def test_reset_defaults_restores_factory(self, qapp_fixture):
        entry = _make_entry(cli_params=[CliParam("--orbit", "轨道", "str", default="halo")])
        store = self._make_param_store(entry)
        le = QLineEdit()
        store._cli_widgets["orbit"] = le
        le.setText("dro")
        gui_defaults: dict[str, Any] = {}
        store.save_defaults(entry, gui_defaults)
        store.reset_defaults(entry, gui_defaults)
        assert le.text() == "halo"
        assert "Test Script" not in gui_defaults

    def test_collect_run_args_checkbox(self, qapp_fixture):
        entry = _make_entry(cli_params=[CliParam("--verbose", "详细", "bool")])
        store = self._make_param_store(entry)
        cb = QCheckBox()
        cb.setChecked(True)
        store._cli_widgets["verbose"] = cb
        assert store.collect_run_args(entry) == ["--verbose"]

    def test_collect_run_args_omits_default(self, qapp_fixture):
        entry = _make_entry(cli_params=[CliParam("--orbit", "轨道", "str", default="halo")])
        store = self._make_param_store(entry)
        le = QLineEdit("halo")
        store._cli_widgets["orbit"] = le
        store._visibility_store._param_defaults[le] = "halo"
        assert store.collect_run_args(entry) == []

    def test_collect_run_args_emits_changed(self, qapp_fixture):
        entry = _make_entry(cli_params=[CliParam("--orbit", "轨道", "str", default="halo")])
        store = self._make_param_store(entry)
        le = QLineEdit("dro")
        store._cli_widgets["orbit"] = le
        store._visibility_store._param_defaults[le] = "halo"
        assert store.collect_run_args(entry) == ["--orbit", "dro"]

    def test_clear_resets_all_dicts(self, qapp_fixture):
        store = self._make_param_store(_make_entry())
        store._cli_widgets["test"] = QWidget()
        store._env_widgets["test"] = QComboBox()
        store._factory_defaults[QWidget()] = "x"
        store.clear()
        assert len(store._cli_widgets) == 0
        assert len(store._env_widgets) == 0
        assert len(store._factory_defaults) == 0

    def test_validate_required_missing(self, qapp_fixture):
        entry = _make_entry(cli_params=[
            CliParam("--dro-file", "DRO 文件", "str", file_category="dro", required=True),
        ])
        store = self._make_param_store(entry)
        combo = QComboBox()
        combo.setEditable(True)
        combo.setEditText("")
        store._cli_widgets["dro_file"] = combo
        with patch.object(QMessageBox, "warning", return_value=QMessageBox.StandardButton.Ok):
            assert store.validate_params(QWidget(), entry) is False

    def test_validate_valid_float(self, qapp_fixture):
        entry = _make_entry(cli_params=[CliParam("--tol", "容差", "float", default="1e-6")])
        store = self._make_param_store(entry)
        store._cli_widgets["tol"] = QLineEdit("1.5e-3")
        assert store.validate_params(QWidget(), entry) is True

    def test_hidden_container_skips_collection(self, qapp_fixture):
        entry = _make_entry(cli_params=[CliParam("--a", "a", "str", default="x")])
        store = self._make_param_store(entry)
        le = QLineEdit("modified")
        store._cli_widgets["a"] = le
        store._visibility_store._param_defaults[le] = "x"
        parent = QWidget()
        parent.show()
        container = QWidget(parent)
        container.setVisible(False)
        store._visibility_store._row_containers["a"] = container
        assert "--a" not in store.collect_run_args(entry)


# ── Facade 向后兼容性测试 ───────────────────────────────────────


class TestFacadeBackwardCompat:
    def test_cli_widgets_property(self, qapp_fixture):
        store = ParamValueStore(files=[], find_cli_param=lambda _: None)
        w = QWidget()
        store._cli_widgets["key"] = w
        assert store._param_store._cli_widgets["key"] is w

    def test_cli_widgets_setter(self, qapp_fixture):
        store = ParamValueStore(files=[], find_cli_param=lambda _: None)
        w = QWidget()
        store._cli_widgets = {"key": w}
        assert store._param_store._cli_widgets["key"] is w

    def test_row_containers_setter(self, qapp_fixture):
        store = ParamValueStore(files=[], find_cli_param=lambda _: None)
        w = QWidget()
        store._row_containers = {"key": w}
        assert store._visibility_store._row_containers["key"] is w

    def test_row_labels_setter(self, qapp_fixture):
        store = ParamValueStore(files=[], find_cli_param=lambda _: None)
        w = QWidget()
        store._row_labels = {"key": w}
        assert store._visibility_store._row_labels["key"] is w

    def test_param_defaults(self, qapp_fixture):
        store = ParamValueStore(files=[], find_cli_param=lambda _: None)
        w = QWidget()
        store._param_defaults[w] = "val"
        assert store._visibility_store._param_defaults[w] == "val"

    def test_widget_factory(self, qapp_fixture):
        store = ParamValueStore(files=[], find_cli_param=lambda _: None)
        assert store.widget_factory is store._param_store._widget_factory
