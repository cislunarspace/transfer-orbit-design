"""ScriptTabWidget — 单脚本参数面板的接口与行为测试。"""

import pytest
from pathlib import Path
from unittest.mock import patch

from PyQt6.QtWidgets import QApplication, QCheckBox, QComboBox, QLineEdit, QSpinBox

from tod.gui.file_discovery import FileInfo
from tod.gui.script_registry import CliParam, ScriptEntry


def _make_entry(**overrides) -> ScriptEntry:
    defaults = dict(
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
        widget._cli_widgets["orbit"].setText("dro")
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
        widget._cli_widgets["iterations"].setValue(200)
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
        widget._cli_widgets["verbose"].setChecked(True)
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
        widget._cli_widgets["orbit"].setText("dro")
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
