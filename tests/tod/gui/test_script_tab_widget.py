"""ScriptTabWidget — 单脚本参数面板的接口与行为测试。"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

from PyQt6.QtWidgets import QApplication, QCheckBox, QComboBox, QLineEdit, QSpinBox, QWidget

from tod.gui.file_discovery import FileInfo
from tod.gui.script_registry import CliParam, ScriptEntry


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


class TestScriptTabWidgetConstruction:
    def test_creates_without_error(self, qapp_fixture, tmp_path):
        from tod.gui.script_tab_widget import ScriptTabWidget

        entry = _make_entry()
        gui_defaults = {}
        widget = ScriptTabWidget(
            entry=entry,
            files=[],
            repo_root=tmp_path,
            gui_defaults=gui_defaults,
            theme_mode="system",
        )
        assert widget.entry is entry

    def test_has_run_button(self, qapp_fixture, tmp_path):
        from tod.gui.script_tab_widget import ScriptTabWidget

        entry = _make_entry()
        widget = ScriptTabWidget(
            entry=entry,
            files=[],
            repo_root=tmp_path,
            gui_defaults={},
            theme_mode="system",
        )
        assert widget._run_btn is not None
        assert widget._run_btn.isEnabled()

    def test_builds_cli_widgets(self, qapp_fixture, tmp_path):
        from tod.gui.script_tab_widget import ScriptTabWidget

        entry = _make_entry(
            cli_params=[
                CliParam("--orbit", "轨道类型", "str", default="halo"),
                CliParam("--iterations", "迭代次数", "int", default="100"),
                CliParam("--verbose", "详细输出", "bool"),
                CliParam("--tolerance", "容差", "float", default="1e-6"),
            ]
        )
        widget = ScriptTabWidget(
            entry=entry,
            files=[],
            repo_root=tmp_path,
            gui_defaults={},
            theme_mode="system",
        )
        assert "orbit" in widget._cli_widgets
        assert "iterations" in widget._cli_widgets
        assert "verbose" in widget._cli_widgets
        assert "tolerance" in widget._cli_widgets

    def test_builds_env_widgets(self, qapp_fixture, tmp_path):
        from tod.gui.script_registry import EnvParam
        from tod.gui.script_tab_widget import ScriptTabWidget

        entry = _make_entry(
            env_params={
                "dro_file": EnvParam("DRO_FILE", "DRO 文件", "dro", "json"),
            }
        )
        widget = ScriptTabWidget(
            entry=entry,
            files=[],
            repo_root=tmp_path,
            gui_defaults={},
            theme_mode="system",
        )
        assert "dro_file" in widget._env_widgets


class TestScriptTabWidgetCollectRunArgs:
    def test_collects_str_arg(self, qapp_fixture, tmp_path):
        from tod.gui.script_tab_widget import ScriptTabWidget

        entry = _make_entry(
            cli_params=[
                CliParam("--orbit", "轨道类型", "str", default="halo"),
            ]
        )
        widget = ScriptTabWidget(
            entry=entry, files=[], repo_root=tmp_path,
            gui_defaults={}, theme_mode="system",
        )
        # 默认值不收集
        args = widget.collect_run_args()
        assert "--orbit" not in args

        # 修改后收集
        cast(QLineEdit, widget._cli_widgets["orbit"]).setText("dro")
        args = widget.collect_run_args()
        assert "--orbit" in args
        assert "dro" in args

    def test_collects_int_arg(self, qapp_fixture, tmp_path):
        from tod.gui.script_tab_widget import ScriptTabWidget

        entry = _make_entry(
            cli_params=[
                CliParam("--iterations", "迭代次数", "int", default="100"),
            ]
        )
        widget = ScriptTabWidget(
            entry=entry, files=[], repo_root=tmp_path,
            gui_defaults={}, theme_mode="system",
        )
        # 出厂默认值 100，改为 200
        cast(QSpinBox, widget._cli_widgets["iterations"]).setValue(200)
        args = widget.collect_run_args()
        assert "--iterations" in args
        assert "200" in args

    def test_collects_bool_arg(self, qapp_fixture, tmp_path):
        from tod.gui.script_tab_widget import ScriptTabWidget

        entry = _make_entry(
            cli_params=[
                CliParam("--verbose", "详细输出", "bool"),
            ]
        )
        widget = ScriptTabWidget(
            entry=entry, files=[], repo_root=tmp_path,
            gui_defaults={}, theme_mode="system",
        )
        # 默认未选中，不收集 flag
        args = widget.collect_run_args()
        assert "--verbose" not in args

        # 选中后收集 flag（无值）
        cast(QCheckBox, widget._cli_widgets["verbose"]).setChecked(True)
        args = widget.collect_run_args()
        assert "--verbose" in args

    def test_skips_hidden_widgets(self, qapp_fixture, tmp_path):
        from tod.gui.script_tab_widget import ScriptTabWidget

        entry = _make_entry(
            cli_params=[
                CliParam("--method", "方法", "str", default="standard"),
                CliParam("--tolerance", "容差", "float", default="1e-6",
                         hidden_when="--method==standard"),
            ]
        )
        widget = ScriptTabWidget(
            entry=entry, files=[], repo_root=tmp_path,
            gui_defaults={}, theme_mode="system",
        )
        # tolerance 被 hidden_when 隐藏，不应被收集
        args = widget.collect_run_args()
        assert "--tolerance" not in args


class TestScriptTabWidgetCollectEnvOverrides:
    def test_collects_env_from_env_widgets(self, qapp_fixture, tmp_path):
        from tod.gui.script_registry import EnvParam
        from tod.gui.script_tab_widget import ScriptTabWidget

        entry = _make_entry(
            env_params={
                "dro_file": EnvParam("DRO_FILE", "DRO 文件", "dro", "json"),
            }
        )
        widget = ScriptTabWidget(
            entry=entry, files=[], repo_root=tmp_path,
            gui_defaults={}, theme_mode="system",
        )
        # 没有选择文件时不应有覆盖
        overrides = widget.collect_env_overrides()
        assert "DRO_FILE" not in overrides


class TestScriptTabWidgetDefaults:
    def test_save_defaults_updates_gui_defaults(self, qapp_fixture, tmp_path):
        from tod.gui.script_tab_widget import ScriptTabWidget

        entry = _make_entry(
            cli_params=[
                CliParam("--orbit", "轨道类型", "str", default="halo"),
            ]
        )
        gui_defaults = {}
        widget = ScriptTabWidget(
            entry=entry, files=[], repo_root=tmp_path,
            gui_defaults=gui_defaults, theme_mode="system",
        )
        cast(QLineEdit, widget._cli_widgets["orbit"]).setText("dro")
        widget._on_save_defaults()

        assert "Test Script" in gui_defaults
        assert gui_defaults["Test Script"]["--orbit"] == "dro"

    def test_reset_defaults_clears_gui_defaults(self, qapp_fixture, tmp_path):
        from tod.gui.script_tab_widget import ScriptTabWidget

        entry = _make_entry(
            cli_params=[
                CliParam("--orbit", "轨道类型", "str", default="halo"),
            ]
        )
        gui_defaults = {"Test Script": {"--orbit": "dro"}}
        widget = ScriptTabWidget(
            entry=entry, files=[], repo_root=tmp_path,
            gui_defaults=gui_defaults, theme_mode="system",
        )
        widget._on_reset_defaults()
        assert "Test Script" not in gui_defaults


class TestScriptTabWidgetSignals:
    def test_run_requested_emitted(self, qapp_fixture, tmp_path):
        from tod.gui.script_tab_widget import ScriptTabWidget

        entry = _make_entry()
        widget = ScriptTabWidget(
            entry=entry, files=[], repo_root=tmp_path,
            gui_defaults={}, theme_mode="system",
        )
        emitted = []
        widget.run_requested.connect(lambda: emitted.append(True))
        widget._run_btn.click()
        assert len(emitted) == 1

    def test_defaults_changed_emitted_on_save(self, qapp_fixture, tmp_path):
        from tod.gui.script_tab_widget import ScriptTabWidget

        entry = _make_entry(
            cli_params=[
                CliParam("--orbit", "轨道类型", "str", default="halo"),
            ]
        )
        widget = ScriptTabWidget(
            entry=entry, files=[], repo_root=tmp_path,
            gui_defaults={}, theme_mode="system",
        )
        emitted = []
        widget.defaults_changed.connect(lambda: emitted.append(True))
        widget._on_save_defaults()
        assert len(emitted) == 1

    def test_defaults_changed_emitted_on_reset(self, qapp_fixture, tmp_path):
        from tod.gui.script_tab_widget import ScriptTabWidget

        entry = _make_entry(
            cli_params=[
                CliParam("--orbit", "轨道类型", "str", default="halo"),
            ]
        )
        widget = ScriptTabWidget(
            entry=entry, files=[], repo_root=tmp_path,
            gui_defaults={}, theme_mode="system",
        )
        emitted = []
        widget.defaults_changed.connect(lambda: emitted.append(True))
        widget._on_reset_defaults()
        assert len(emitted) == 1


class _Harness:
    """Minimal harness exposing the attributes _setup_conditional_visibility needs.

    Calls the real ScriptTabWidget._setup_conditional_visibility as a bound method
    to drive the production code path without spinning up a full ScriptTabWidget.
    """

    def __init__(self):
        self._cli_widgets: dict[str, QWidget] = {}
        self._cli_row_containers: dict[str, QWidget] = {}
        self._cli_row_labels: dict[str, QWidget] = {}
        self._current_script: ScriptEntry | None = None

    def _setup_conditional_visibility(self, entry: ScriptEntry) -> None:
        from tod.gui.script_tab_widget import ScriptTabWidget
        return ScriptTabWidget._setup_conditional_visibility(self, entry)

    def _find_cli_param(self, key: str) -> CliParam | None:
        if self._current_script is None:
            return None
        for p in self._current_script.cli_params:
            if p.flag.lstrip("-").replace("-", "_") == key:
                return p
        return None


def _make_entry_with_params(params: list[CliParam]) -> ScriptEntry:
    return ScriptEntry(
        module="test",
        name="test_script",
        description="test",
        script_path="test.py",
        cli_params=params,
    )


class TestHiddenWhenValueCondition:
    """Test hidden_when ==value syntax for conditional visibility (issue #123).

    Drives the real ScriptTabWidget._setup_conditional_visibility via either a
    lightweight _Harness (unit-style) or a full ScriptTabWidget (end-to-end).
    """

    def test_combobox_matching_value_hides_target(self, qapp_fixture):
        """When trigger QComboBox currentText matches ==value, target is hidden."""
        from tod.gui.script_tab_widget import ScriptTabWidget

        trigger = QComboBox()
        trigger.addItems(["natural", "pseudo_arclength"])
        trigger.setCurrentText("natural")

        target_container = QWidget()
        target_container.setVisible(True)
        target_label = QWidget()
        target_label.setVisible(True)

        harness = _Harness()
        harness._cli_widgets = {"method": trigger, "step_size_negative": QWidget()}
        harness._cli_row_containers = {"step_size_negative": target_container}
        harness._cli_row_labels = {"step_size_negative": target_label}

        entry = _make_entry_with_params([
            CliParam("--method", "Method", "str", "natural",
                     choices=("natural", "pseudo_arclength")),
            CliParam("--step-size-negative", "Neg step", "float", "0.009",
                     hidden_when="--method==natural"),
        ])
        harness._current_script = entry
        ScriptTabWidget._setup_conditional_visibility(harness, entry)

        assert not target_container.isVisible()
        assert not target_label.isVisible()

    def test_combobox_non_matching_value_shows_target(self, qapp_fixture):
        """When trigger QComboBox currentText does NOT match ==value, target is visible."""
        from tod.gui.script_tab_widget import ScriptTabWidget

        trigger = QComboBox()
        trigger.addItems(["natural", "pseudo_arclength"])
        trigger.setCurrentText("pseudo_arclength")

        target_container = QWidget()
        target_container.setVisible(True)
        target_label = QWidget()
        target_label.setVisible(True)

        harness = _Harness()
        harness._cli_widgets = {"method": trigger, "step_size_negative": QWidget()}
        harness._cli_row_containers = {"step_size_negative": target_container}
        harness._cli_row_labels = {"step_size_negative": target_label}

        entry = _make_entry_with_params([
            CliParam("--method", "Method", "str", "natural",
                     choices=("natural", "pseudo_arclength")),
            CliParam("--step-size-negative", "Neg step", "float", "0.009",
                     hidden_when="--method==natural"),
        ])
        harness._current_script = entry
        ScriptTabWidget._setup_conditional_visibility(harness, entry)

        assert target_container.isVisible()
        assert target_label.isVisible()

    def test_combobox_signal_toggles_visibility(self, qapp_fixture):
        """Changing trigger QComboBox value toggles target visibility."""
        from tod.gui.script_tab_widget import ScriptTabWidget

        trigger = QComboBox()
        trigger.addItems(["natural", "pseudo_arclength"])
        trigger.setCurrentText("natural")

        target_container = QWidget()
        target_container.setVisible(True)

        harness = _Harness()
        harness._cli_widgets = {"method": trigger, "step_size_negative": QWidget()}
        harness._cli_row_containers = {"step_size_negative": target_container}
        harness._cli_row_labels = {"step_size_negative": QWidget()}

        entry = _make_entry_with_params([
            CliParam("--method", "Method", "str", "natural",
                     choices=("natural", "pseudo_arclength")),
            CliParam("--step-size-negative", "Neg step", "float", "0.009",
                     hidden_when="--method==natural"),
        ])
        harness._current_script = entry
        ScriptTabWidget._setup_conditional_visibility(harness, entry)

        assert not target_container.isVisible()

        trigger.setCurrentText("pseudo_arclength")
        assert target_container.isVisible()

        trigger.setCurrentText("natural")
        assert not target_container.isVisible()

    def test_backward_compat_presence_check_still_works(self, qapp_fixture):
        """Old-style hidden_when (no ==value) still works as presence check."""
        from tod.gui.script_tab_widget import ScriptTabWidget

        trigger = QComboBox()
        trigger.addItem("")
        trigger.addItem("some_file.json")
        trigger.setCurrentText("")

        target_container = QWidget()
        target_container.setVisible(True)
        target_label = QWidget()
        target_label.setVisible(True)

        harness = _Harness()
        harness._cli_widgets = {"seed_file": trigger, "amplitude_z": QWidget()}
        harness._cli_row_containers = {"amplitude_z": target_container}
        harness._cli_row_labels = {"amplitude_z": target_label}

        entry = _make_entry_with_params([
            CliParam("--seed-file", "Seed", "str"),
            CliParam("--amplitude-z", "Amp", "float", "0.23",
                     hidden_when="--seed-file"),
        ])
        harness._current_script = entry
        ScriptTabWidget._setup_conditional_visibility(harness, entry)

        assert target_container.isVisible()

        trigger.setCurrentText("some_file.json")
        assert not target_container.isVisible()

    def test_multiple_targets_share_one_trigger(self, qapp_fixture):
        """Multiple params with hidden_when referencing the same trigger."""
        from tod.gui.script_tab_widget import ScriptTabWidget

        trigger = QComboBox()
        trigger.addItems(["natural", "pseudo_arclength"])
        trigger.setCurrentText("pseudo_arclength")

        container_a = QWidget()
        container_a.setVisible(True)
        container_b = QWidget()
        container_b.setVisible(True)

        harness = _Harness()
        harness._cli_widgets = {
            "method": trigger,
            "z_min": QWidget(),
            "z_max": QWidget(),
        }
        harness._cli_row_containers = {"z_min": container_a, "z_max": container_b}
        harness._cli_row_labels = {"z_min": QWidget(), "z_max": QWidget()}

        entry = _make_entry_with_params([
            CliParam("--method", "Method", "str", "pseudo_arclength",
                     choices=("natural", "pseudo_arclength")),
            CliParam("--z-min", "Z min", "float", "0.001",
                     hidden_when="--method==pseudo_arclength"),
            CliParam("--z-max", "Z max", "float", "0.5",
                     hidden_when="--method==pseudo_arclength"),
        ])
        harness._current_script = entry
        ScriptTabWidget._setup_conditional_visibility(harness, entry)

        assert not container_a.isVisible()
        assert not container_b.isVisible()

        trigger.setCurrentText("natural")
        assert container_a.isVisible()
        assert container_b.isVisible()

    def test_checkbox_boolean_comparison(self, qapp_fixture):
        """hidden_when with ==True/==False works for QCheckBox trigger."""
        from tod.gui.script_tab_widget import ScriptTabWidget

        trigger = QCheckBox()
        trigger.setChecked(True)

        target_container = QWidget()
        target_container.setVisible(True)

        harness = _Harness()
        harness._cli_widgets = {"verbose": trigger, "extra": QWidget()}
        harness._cli_row_containers = {"extra": target_container}
        harness._cli_row_labels = {}

        entry = _make_entry_with_params([
            CliParam("--verbose", "Verbose", "bool"),
            CliParam("--extra", "Extra", "str", hidden_when="--verbose==True"),
        ])
        harness._current_script = entry
        ScriptTabWidget._setup_conditional_visibility(harness, entry)

        assert not target_container.isVisible()

        trigger.setChecked(False)
        assert target_container.isVisible()

    def test_lineedit_value_comparison(self, qapp_fixture):
        """hidden_when with ==value works for QLineEdit trigger."""
        from tod.gui.script_tab_widget import ScriptTabWidget

        trigger = QLineEdit("auto")

        target_container = QWidget()
        target_container.setVisible(True)

        harness = _Harness()
        harness._cli_widgets = {"mode": trigger, "threshold": QWidget()}
        harness._cli_row_containers = {"threshold": target_container}
        harness._cli_row_labels = {}

        entry = _make_entry_with_params([
            CliParam("--mode", "Mode", "str", "auto"),
            CliParam("--threshold", "Threshold", "float", "0.5",
                     hidden_when="--mode==auto"),
        ])
        harness._current_script = entry
        ScriptTabWidget._setup_conditional_visibility(harness, entry)

        assert not target_container.isVisible()

        trigger.setText("manual")
        assert target_container.isVisible()

    def test_choice_values_reverse_mapping_in_condition(self, qapp_fixture):
        """When trigger QComboBox uses choice_values, ==value compares CLI value, not display text."""
        from tod.gui.script_tab_widget import ScriptTabWidget

        trigger = QComboBox()
        trigger.addItems(["北族", "南族"])
        trigger.setCurrentText("北族")

        target_container = QWidget()
        target_container.setVisible(True)

        harness = _Harness()
        harness._cli_widgets = {"halo_class": trigger, "extra": QWidget()}
        harness._cli_row_containers = {"extra": target_container}
        harness._cli_row_labels = {}

        entry = _make_entry_with_params([
            CliParam("--halo-class", "Class", "str", "0",
                     choices=("北族", "南族"),
                     choice_values={"北族": "0", "南族": "1"}),
            CliParam("--extra", "Extra", "str", hidden_when="--halo-class==0"),
        ])
        harness._current_script = entry
        ScriptTabWidget._setup_conditional_visibility(harness, entry)

        assert not target_container.isVisible()

        trigger.setCurrentText("南族")
        assert target_container.isVisible()

    def test_end_to_end_via_setup_ui(self, qapp_fixture, tmp_path):
        """End-to-end: building a real ScriptTabWidget wires up conditional visibility."""
        from tod.gui.script_tab_widget import ScriptTabWidget

        entry = _make_entry(
            cli_params=[
                CliParam("--method", "Method", "str", "natural",
                         choices=("natural", "pseudo_arclength")),
                CliParam("--step-size-negative", "Neg step", "float", "0.009",
                         hidden_when="--method==natural"),
                CliParam("--seed-file", "Seed", "str"),
                CliParam("--amplitude-z", "Amp", "float", "0.23",
                         hidden_when="--seed-file"),
            ]
        )
        widget = ScriptTabWidget(
            entry=entry, files=[], repo_root=tmp_path,
            gui_defaults={}, theme_mode="system",
        )
        widget.show()

        # Initially: method="natural" hides --step-size-negative,
        # seed-file="" shows --amplitude-z.
        assert "step_size_negative" in widget._cli_row_containers
        assert "amplitude_z" in widget._cli_row_containers
        step_container = widget._cli_row_containers["step_size_negative"]
        amp_container = widget._cli_row_containers["amplitude_z"]
        # isHidden() reflects the explicit setVisible state independent of
        # whether the top-level window is shown.
        assert step_container.isHidden()
        assert not amp_container.isHidden()

        # Flip method → step container becomes visible again.
        cast(QComboBox, widget._cli_widgets["method"]).setCurrentText("pseudo_arclength")
        assert not step_container.isHidden()

        # Fill seed-file → amplitude_z becomes hidden.
        cast(QLineEdit, widget._cli_widgets["seed_file"]).setText("seed.json")
        assert amp_container.isHidden()
