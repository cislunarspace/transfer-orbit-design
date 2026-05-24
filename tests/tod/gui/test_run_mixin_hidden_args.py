"""Tests for run_mixin hidden widget exclusion from extra_args — issue #123."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from unittest.mock import MagicMock, patch

import pytest

from PyQt6.QtWidgets import QApplication, QComboBox, QLineEdit, QWidget

from tod.gui.script_registry import CliParam, ScriptEntry


def _qapp():
    app = QApplication.instance()
    if app is None:
        return QApplication([])
    return app


@pytest.fixture(autouse=True)
def _ensure_qapp():
    return _qapp()


class _Harness:
    """Minimal harness for _on_run with hidden widget filtering."""

    def __init__(self):
        self._cli_widgets: dict[str, QWidget] = {}
        self._cli_row_containers: dict[str, QWidget] = {}
        self._chip_widgets: dict[str, QWidget] = {}
        self._multi_file_widgets: dict[str, QWidget] = {}
        self._env_widgets: dict[str, QWidget] = {}
        self._current_script: ScriptEntry | None = None
        self._param_defaults: dict[QWidget, str] = {}
        self._factory_defaults: dict[QWidget, str] = {}
        self._current_theme_mode = "system"
        self._gui_defaults: dict = {}
        self._job_manager = MagicMock()
        self._widget_factory = MagicMock()
        self._widget_factory.unit_combos = {}
        self._file_tree = MagicMock()
        self._find_cli_param = MagicMock(return_value=None)
        self._validate_params = MagicMock(return_value=True)

    def _collect_chip_selections(self) -> dict[str, list[str]]:
        return {}

    def _collect_multi_file_configs(self) -> dict[str, list[dict]]:
        return {}

    def _expand_combinations(self, base_args, chip_selections):
        return [base_args]


class TestRunMixinSkipsHiddenWidgets:
    """Hidden widget containers should be excluded from extra_args."""

    def test_visible_widget_value_included_in_extra_args(self):
        from tod.gui.run_mixin import RunMixin

        widget = QComboBox()
        widget.addItems(["", "L2"])
        widget.setCurrentText("L2")

        container = QWidget()
        container.setVisible(True)

        cli_param = CliParam("--libration-point", "LP", "str", "L1",
                             choices=("L1", "L2", "L3"))

        harness = _Harness()
        harness._cli_widgets = {"libration_point": widget}
        harness._cli_row_containers = {"libration_point": container}
        harness._current_script = ScriptEntry(
            module="test", name="t", description="t", script_path="t.py",
        )
        harness._param_defaults = {widget: "L1"}
        harness._find_cli_param = MagicMock(return_value=cli_param)

        with (
            patch("tod.gui.run_mixin.plot_font_env_from_settings", return_value={}),
            patch("tod.gui.run_mixin.body_icon_env_from_settings", return_value={}),
        ):
            RunMixin._on_run(harness)

        call_args = harness._job_manager.start_job.call_args
        assert call_args is not None
        extra_args = call_args[0][1]
        assert "--libration-point" in extra_args
        assert "L2" in extra_args

    def test_hidden_widget_value_excluded_from_extra_args(self):
        from tod.gui.run_mixin import RunMixin

        visible_widget = QComboBox()
        visible_widget.addItems(["", "L2"])
        visible_widget.setCurrentText("L2")

        hidden_widget = QLineEdit("0.001")

        visible_container = QWidget()
        visible_container.setVisible(True)

        hidden_container = QWidget()
        hidden_container.setVisible(False)

        visible_param = CliParam("--libration-point", "LP", "str", "L1",
                                 choices=("L1", "L2", "L3"))
        hidden_param = CliParam("--z-min", "Z min", "float", "0.001")

        harness = _Harness()
        harness._cli_widgets = {
            "libration_point": visible_widget,
            "z_min": hidden_widget,
        }
        harness._cli_row_containers = {
            "libration_point": visible_container,
            "z_min": hidden_container,
        }
        harness._current_script = ScriptEntry(
            module="test", name="t", description="t", script_path="t.py",
        )
        harness._param_defaults = {visible_widget: "L1", hidden_widget: "0.001"}

        def find_param(key):
            if key == "libration_point":
                return visible_param
            if key == "z_min":
                return hidden_param
            return None

        harness._find_cli_param = MagicMock(side_effect=find_param)

        with (
            patch("tod.gui.run_mixin.plot_font_env_from_settings", return_value={}),
            patch("tod.gui.run_mixin.body_icon_env_from_settings", return_value={}),
        ):
            RunMixin._on_run(harness)

        call_args = harness._job_manager.start_job.call_args
        extra_args = call_args[0][1]
        assert "--libration-point" in extra_args
        assert "--z-min" not in extra_args
