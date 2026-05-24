# pyright: reportArgumentType=false, reportOptionalMemberAccess=false, reportAttributeAccessIssue=false, reportGeneralTypeIssues=false
"""Tests for hidden_when ==value conditional visibility — issue #123."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from PyQt6.QtWidgets import QApplication, QCheckBox, QComboBox, QLineEdit, QWidget

from tod.gui.script_registry import CliParam, ScriptEntry


class _Harness:
    """Minimal harness exposing the attributes _setup_conditional_visibility needs."""

    def __init__(self):
        self._cli_widgets: dict[str, QWidget] = {}
        self._cli_row_containers: dict[str, QWidget] = {}
        self._cli_row_labels: dict[str, QWidget] = {}
        self._current_script: ScriptEntry | None = None

    def _setup_conditional_visibility(self, entry: ScriptEntry) -> None:
        from tod.gui.params_panel_mixin import ParamsPanelMixin
        return ParamsPanelMixin._setup_conditional_visibility(self, entry)

    def _find_cli_param(self, key: str) -> CliParam | None:
        if self._current_script is None:
            return None
        for p in self._current_script.cli_params:
            if p.flag.lstrip("-").replace("-", "_") == key:
                return p
        return None


def _make_entry(params: list[CliParam]) -> ScriptEntry:
    return ScriptEntry(
        module="test",
        name="test_script",
        description="test",
        script_path="test.py",
        cli_params=params,
    )


class TestHiddenWhenValueCondition:
    """Test hidden_when ==value syntax for conditional visibility."""

    @pytest.fixture(autouse=True)
    def _ensure_qapp(self, qapp):
        pass

    def test_combobox_matching_value_hides_target(self, qapp):
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

        entry = _make_entry([
            CliParam("--method", "Method", "str", "natural",
                     choices=("natural", "pseudo_arclength")),
            CliParam("--step-size-negative", "Neg step", "float", "0.009",
                     hidden_when="--method==natural"),
        ])
        harness._current_script = entry
        harness._setup_conditional_visibility(entry)

        assert not target_container.isVisible()
        assert not target_label.isVisible()

    def test_combobox_non_matching_value_shows_target(self, qapp):
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

        entry = _make_entry([
            CliParam("--method", "Method", "str", "natural",
                     choices=("natural", "pseudo_arclength")),
            CliParam("--step-size-negative", "Neg step", "float", "0.009",
                     hidden_when="--method==natural"),
        ])
        harness._current_script = entry
        harness._setup_conditional_visibility(entry)

        assert target_container.isVisible()
        assert target_label.isVisible()

    def test_combobox_signal_toggles_visibility(self, qapp):
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

        entry = _make_entry([
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

    def test_backward_compat_presence_check_still_works(self, qapp):
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

        entry = _make_entry([
            CliParam("--seed-file", "Seed", "str"),
            CliParam("--amplitude-z", "Amp", "float", "0.23",
                     hidden_when="--seed-file"),
        ])
        harness._current_script = entry
        harness._setup_conditional_visibility(entry)

        assert target_container.isVisible()

        trigger.setCurrentText("some_file.json")
        assert not target_container.isVisible()

    def test_multiple_targets_share_one_trigger(self, qapp):
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

        entry = _make_entry([
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

    def test_checkbox_boolean_comparison(self, qapp):
        """hidden_when with ==True/==False works for QCheckBox trigger."""
        trigger = QCheckBox()
        trigger.setChecked(True)

        target_container = QWidget()
        target_container.setVisible(True)

        harness = _Harness()
        harness._cli_widgets = {"verbose": trigger, "extra": QWidget()}
        harness._cli_row_containers = {"extra": target_container}
        harness._cli_row_labels = {}

        entry = _make_entry([
            CliParam("--verbose", "Verbose", "bool"),
            CliParam("--extra", "Extra", "str", hidden_when="--verbose==True"),
        ])
        harness._current_script = entry
        harness._setup_conditional_visibility(entry)

        assert not target_container.isVisible()

        trigger.setChecked(False)
        assert target_container.isVisible()

    def test_lineedit_value_comparison(self, qapp):
        """hidden_when with ==value works for QLineEdit trigger."""
        trigger = QLineEdit("auto")

        target_container = QWidget()
        target_container.setVisible(True)

        harness = _Harness()
        harness._cli_widgets = {"mode": trigger, "threshold": QWidget()}
        harness._cli_row_containers = {"threshold": target_container}
        harness._cli_row_labels = {}

        entry = _make_entry([
            CliParam("--mode", "Mode", "str", "auto"),
            CliParam("--threshold", "Threshold", "float", "0.5",
                     hidden_when="--mode==auto"),
        ])
        harness._current_script = entry
        harness._setup_conditional_visibility(entry)

        assert not target_container.isVisible()

        trigger.setText("manual")
        assert target_container.isVisible()

    def test_choice_values_reverse_mapping_in_condition(self, qapp):
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

        entry = _make_entry([
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
