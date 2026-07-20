"""ScriptTabWidget — 单脚本参数面板的接口与行为测试。"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from typing import Any, cast

from PyQt6.QtWidgets import QApplication, QCheckBox, QComboBox, QLineEdit, QSpinBox, QWidget

from tod.gui.params.param_value_store import ParamValueStore
from tod.scripting import CatalogSeedSelectorParam, CliParam, ScriptEntry


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
        assert "orbit" in widget._store._cli_widgets
        assert "iterations" in widget._store._cli_widgets
        assert "verbose" in widget._store._cli_widgets
        assert "tolerance" in widget._store._cli_widgets

    def test_builds_env_widgets(self, qapp_fixture, tmp_path):
        from tod.scripting import EnvParam
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
        assert "dro_file" in widget._store._env_widgets


class TestCatalogSeedSelectorDefaults:
    def test_catalog_selector_defaults_to_manual_mode_without_loading_catalog(self, qapp_fixture, tmp_path):
        from tod.gui.script_tab_widget import ScriptTabWidget

        entry = _make_entry(
            catalog_seed_selectors=[
                CatalogSeedSelectorParam(
                    key="dro_catalog_seed",
                    label="DRO 参考初值",
                    orbit_type="dro",
                )
            ],
            cli_params=[
                CliParam("--x0", "初始 x 坐标", "float", "1.1202", unit_group="distance", default_unit="DU"),
                CliParam("--vy0", "初始 vy 速度", "float", "-0.4618", unit_group="velocity"),
                CliParam("--period", "目标周期", "float", "2.095", unit_group="time"),
                CliParam("--seed-id", "参考记录编号", "str", ""),
                CliParam("--jacobi", "Jacobi", "float", ""),
            ],
        )
        widget = ScriptTabWidget(entry=entry, files=[], repo_root=tmp_path, gui_defaults={}, theme_mode="system")

        state = widget._store._catalog_seed_selectors["dro_catalog_seed"]
        assert not state.enabled_checkbox.isChecked()
        assert not state.selector_widget.isEnabled()
        for key in ("x0", "vy0", "period"):
            manual_widget = widget._store._cli_widgets[key]
            assert manual_widget.isEnabled()
            assert widget._store._widget_factory.display_widget(manual_widget).isEnabled()

        args = widget.collect_run_args()
        assert "--seed-id" not in args
        assert "--jacobi" not in args


    def test_catalog_selector_unchecked_skips_seed_and_jacobi_even_if_fields_have_text(self, qapp_fixture, tmp_path):
        from tod.gui.script_tab_widget import ScriptTabWidget

        entry = _make_entry(
            catalog_seed_selectors=[
                CatalogSeedSelectorParam(
                    key="dro_catalog_seed",
                    label="DRO 参考初值",
                    orbit_type="dro",
                )
            ],
            cli_params=[
                CliParam("--x0", "初始 x 坐标", "float", "1.1202"),
                CliParam("--vy0", "初始 vy 速度", "float", "-0.4618"),
                CliParam("--period", "目标周期", "float", "2.095"),
                CliParam("--seed-id", "参考记录编号", "str", ""),
                CliParam("--jacobi", "Jacobi", "float", ""),
                CliParam("--jacobi-tolerance", "Jacobi 容差", "float", ""),
            ],
        )
        widget = ScriptTabWidget(entry=entry, files=[], repo_root=tmp_path, gui_defaults={}, theme_mode="system")

        cast(QLineEdit, widget._store._cli_widgets["seed_id"]).setText("earth-moon_dro:000001")
        cast(QLineEdit, widget._store._cli_widgets["jacobi"]).setText("3.1")
        cast(QLineEdit, widget._store._cli_widgets["jacobi_tolerance"]).setText("1e-4")

        args = widget.collect_run_args()

        assert "--seed-id" not in args
        assert "--jacobi" not in args
        assert "--jacobi-tolerance" not in args


    def test_catalog_selector_checkbox_toggles_manual_and_selector_widgets(self, qapp_fixture, tmp_path):
        from tod.gui.script_tab_widget import ScriptTabWidget

        entry = _make_entry(
            catalog_seed_selectors=[
                CatalogSeedSelectorParam(
                    key="dro_catalog_seed",
                    label="DRO 参考初值",
                    orbit_type="dro",
                )
            ],
            cli_params=[
                CliParam("--x0", "初始 x 坐标", "float", "1.1202", unit_group="distance", default_unit="DU"),
                CliParam("--vy0", "初始 vy 速度", "float", "-0.4618", unit_group="velocity"),
                CliParam("--period", "目标周期", "float", "2.095", unit_group="time"),
                CliParam("--seed-id", "参考记录编号", "str", ""),
                CliParam("--jacobi", "Jacobi", "float", ""),
            ],
        )
        widget = ScriptTabWidget(entry=entry, files=[], repo_root=tmp_path, gui_defaults={}, theme_mode="system")
        state = widget._store._catalog_seed_selectors["dro_catalog_seed"]

        state.enabled_checkbox.setChecked(True)

        assert state.selector_widget.isEnabled()
        for key in ("x0", "vy0", "period"):
            manual_widget = widget._store._cli_widgets[key]
            assert not manual_widget.isEnabled()
            assert not widget._store._widget_factory.display_widget(manual_widget).isEnabled()

        state.enabled_checkbox.setChecked(False)

        assert not state.selector_widget.isEnabled()
        for key in ("x0", "vy0", "period"):
            manual_widget = widget._store._cli_widgets[key]
            assert manual_widget.isEnabled()
            assert widget._store._widget_factory.display_widget(manual_widget).isEnabled()


    def test_catalog_selector_enabled_collects_selected_seed_id_arg(self, qapp_fixture, tmp_path):
        from tod.gui.script_tab_widget import ScriptTabWidget

        entry = _make_entry(
            catalog_seed_selectors=[
                CatalogSeedSelectorParam(
                    key="dro_catalog_seed",
                    label="DRO 参考初值",
                    orbit_type="dro",
                )
            ],
            cli_params=[
                CliParam("--x0", "初始 x 坐标", "float", "1.1202"),
                CliParam("--vy0", "初始 vy 速度", "float", "-0.4618"),
                CliParam("--period", "目标周期", "float", "2.095"),
                CliParam("--seed-id", "参考记录编号", "str", ""),
                CliParam("--jacobi", "Jacobi", "float", ""),
            ],
        )
        widget = ScriptTabWidget(entry=entry, files=[], repo_root=tmp_path, gui_defaults={}, theme_mode="system")
        state = widget._store._catalog_seed_selectors["dro_catalog_seed"]
        cast(QComboBox, state.selector_widget).addItem(
            "earth-moon_dro:000001 | C=3.1 | T=7.0",
            "earth-moon_dro:000001",
        )

        state.enabled_checkbox.setChecked(True)
        cast(QComboBox, state.selector_widget).setCurrentIndex(1)
        args = widget.collect_run_args()

        assert args == ["--seed-id", "earth-moon_dro:000001"]


    def test_catalog_selector_jacobi_mode_collects_jacobi_args(self, qapp_fixture, tmp_path):
        from tod.gui.script_tab_widget import ScriptTabWidget

        entry = _make_entry(
            catalog_seed_selectors=[CatalogSeedSelectorParam(key="dro_catalog_seed", label="DRO 参考初值", orbit_type="dro")],
            cli_params=[
                CliParam("--x0", "初始 x 坐标", "float", "1.1202"),
                CliParam("--vy0", "初始 vy 速度", "float", "-0.4618"),
                CliParam("--period", "目标周期", "float", "2.095"),
                CliParam("--seed-id", "参考记录编号", "str", ""),
                CliParam("--jacobi", "Jacobi", "float", ""),
                CliParam("--jacobi-tolerance", "Jacobi 容差", "float", ""),
            ],
        )
        widget = ScriptTabWidget(entry=entry, files=[], repo_root=tmp_path, gui_defaults={}, theme_mode="system")
        state = widget._store._catalog_seed_selectors["dro_catalog_seed"]

        state.mode_widget.setCurrentIndex(state.mode_widget.findData("jacobi_match"))
        state.enabled_checkbox.setChecked(True)
        state.jacobi_widget.setText("3.10005")
        assert widget.collect_run_args() == ["--jacobi", "3.10005"]

        state.tolerance_widget.setText("1e-4")
        assert widget.collect_run_args() == ["--jacobi", "3.10005", "--jacobi-tolerance", "1e-4"]


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
        cast(QLineEdit, widget._store._cli_widgets["orbit"]).setText("dro")
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
        cast(QSpinBox, widget._store._cli_widgets["iterations"]).setValue(200)
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
        cast(QCheckBox, widget._store._cli_widgets["verbose"]).setChecked(True)
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
        from tod.scripting import EnvParam
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
        cast(QLineEdit, widget._store._cli_widgets["orbit"]).setText("dro")
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

    Calls the real ParamValueStore.setup_conditional_visibility to drive the
    production code path without spinning up a full ScriptTabWidget.
    """

    def __init__(self):
        self._cli_widgets: dict[str, QWidget] = {}
        self._cli_row_containers: dict[str, QWidget] = {}
        self._cli_row_labels: dict[str, QWidget] = {}
        self._current_script: ScriptEntry | None = None
        self._store = ParamValueStore(
            files=[],
            find_cli_param=self._find_cli_param,
        )

    def _setup_conditional_visibility(self, entry: ScriptEntry) -> None:
        self._store.setup_conditional_visibility(
            entry,
            cli_widgets=self._cli_widgets,
            row_containers=self._cli_row_containers,
            row_labels=self._cli_row_labels,
        )

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

    Drives the real ParamValueStore.setup_conditional_visibility via either a
    lightweight _Harness (unit-style) or a full ScriptTabWidget (end-to-end).
    """

    def test_combobox_matching_value_hides_target(self, qapp_fixture):
        """When trigger QComboBox currentText matches ==value, target is hidden."""

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
        harness._setup_conditional_visibility(entry)

        assert not target_container.isVisible()
        assert not target_label.isVisible()

    def test_combobox_non_matching_value_shows_target(self, qapp_fixture):
        """When trigger QComboBox currentText does NOT match ==value, target is visible."""

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
        harness._setup_conditional_visibility(entry)

        assert target_container.isVisible()
        assert target_label.isVisible()

    def test_combobox_signal_toggles_visibility(self, qapp_fixture):
        """Changing trigger QComboBox value toggles target visibility."""

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
        harness._setup_conditional_visibility(entry)

        assert not target_container.isVisible()

        trigger.setCurrentText("pseudo_arclength")
        assert target_container.isVisible()

        trigger.setCurrentText("natural")
        assert not target_container.isVisible()

    def test_backward_compat_presence_check_still_works(self, qapp_fixture):
        """Old-style hidden_when (no ==value) still works as presence check."""

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
        harness._setup_conditional_visibility(entry)

        assert target_container.isVisible()

        trigger.setCurrentText("some_file.json")
        assert not target_container.isVisible()

    def test_multiple_targets_share_one_trigger(self, qapp_fixture):
        """Multiple params with hidden_when referencing the same trigger."""

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
        harness._setup_conditional_visibility(entry)

        assert not container_a.isVisible()
        assert not container_b.isVisible()

        trigger.setCurrentText("natural")
        assert container_a.isVisible()
        assert container_b.isVisible()

    def test_checkbox_boolean_comparison(self, qapp_fixture):
        """hidden_when with ==True/==False works for QCheckBox trigger."""

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
        harness._setup_conditional_visibility(entry)

        assert not target_container.isVisible()

        trigger.setChecked(False)
        assert target_container.isVisible()

    def test_lineedit_value_comparison(self, qapp_fixture):
        """hidden_when with ==value works for QLineEdit trigger."""

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
        harness._setup_conditional_visibility(entry)

        assert not target_container.isVisible()

        trigger.setText("manual")
        assert target_container.isVisible()

    def test_choice_values_reverse_mapping_in_condition(self, qapp_fixture):
        """When trigger QComboBox uses choice_values, ==value compares CLI value, not display text."""

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
        harness._setup_conditional_visibility(entry)

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
        assert "step_size_negative" in widget._store._row_containers
        assert "amplitude_z" in widget._store._row_containers
        step_container = widget._store._row_containers["step_size_negative"]
        amp_container = widget._store._row_containers["amplitude_z"]
        # isHidden() reflects the explicit setVisible state independent of
        # whether the top-level window is shown.
        assert step_container.isHidden()
        assert not amp_container.isHidden()

        # Flip method → step container becomes visible again.
        cast(QComboBox, widget._store._cli_widgets["method"]).setCurrentText("pseudo_arclength")
        assert not step_container.isHidden()

        # Fill seed-file → amplitude_z becomes hidden.
        cast(QLineEdit, widget._store._cli_widgets["seed_file"]).setText("seed.json")
        assert amp_container.isHidden()


# 禁用术语白名单:HITL 审定初始名单 (issue #196)。
# DRO Generate 面板任何面向用户可见文本(QLabel text、QLineEdit placeholder、
# QCheckBox text、QComboBox item text)不得出现下列术语。实现细节术语
# (normalized / raw XLSX / importer)按 ADR-0002 + CONTEXT.md 允许保留。
_DRO_GUI_FORBIDDEN_TERMS = (
    "Seed ID",
    "Catalog 初值",
    "Catalog 种子",
    "Jacobi nearest-neighbor",
    "nearest-neighbor",
    "Catalog 目录",
    "禁用自动导入 catalog",
    "加载 Catalog",
    "raw/normalized catalog",
)


def _collect_dro_gui_visible_texts(widget) -> list[tuple[str, str]]:
    """遍历 widget 树,收集所有面向用户的可见文本。

    返回 [(widget_class, text), ...] 列表;QComboBox 展开每个 item text。
    """
    from PyQt6.QtWidgets import QComboBox, QWidget

    collected: list[tuple[str, str]] = []

    def walk(node: QWidget) -> None:
        cls_name = type(node).__name__
        text = node.text() if hasattr(node, "text") else ""
        if callable(text):
            try:
                text = text()
            except Exception:
                text = ""
        if text:
            collected.append((cls_name, str(text)))
        if hasattr(node, "placeholderText"):
            try:
                placeholder = node.placeholderText()
            except Exception:
                placeholder = ""
            if placeholder:
                collected.append((cls_name + ".placeholder", str(placeholder)))
        if isinstance(node, QComboBox):
            for i in range(node.count()):
                item_text = node.itemText(i)
                if item_text:
                    collected.append((cls_name + ".item", str(item_text)))
        for child in node.children():
            if isinstance(child, QWidget):
                walk(child)

    walk(widget)
    return collected


class TestDroGuiTerminologySnapshot:
    """DRO Generate GUI 可见文本不得含禁用术语。

    锁住 issue #196 的白名单:任何未来回归(把 Seed ID 写回 label 等)
    都会被此测试捕获。白名单范围由 HITL 审定。
    """

    def test_dro_gui_has_no_forbidden_user_terms(self, qapp_fixture, tmp_path):
        from tod.generates.cr3bp.dro.generate_dro_orbit import SCRIPT_ENTRY
        from tod.gui.script_tab_widget import ScriptTabWidget

        widget = ScriptTabWidget(
            entry=SCRIPT_ENTRY,
            files=[],
            repo_root=tmp_path,
            gui_defaults={},
            theme_mode="system",
        )
        visible_texts = _collect_dro_gui_visible_texts(widget)

        offenders: list[tuple[str, str, str]] = []
        for source, text in visible_texts:
            for forbidden in _DRO_GUI_FORBIDDEN_TERMS:
                if forbidden in text:
                    offenders.append((forbidden, source, text))

        assert not offenders, (
            "DRO Generate GUI 含禁用术语 (issue #196 白名单):\n"
            + "\n".join(f"  {term!r} in {src}: {text!r}" for term, src, text in offenders)
        )
