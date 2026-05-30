# pyright: reportArgumentType=false, reportOptionalMemberAccess=false, reportAttributeAccessIssue=false, reportGeneralTypeIssues=false
"""run_mixin — 运行与验证 Mixin 的接口测试。"""

from unittest.mock import MagicMock, patch

import pytest

from tod.gui.script_registry import CliChipParam, CliParam, ScriptEntry


class TestRunMixinImportable:
    def test_mixin_importable(self):
        from tod.gui.run_mixin import RunMixin
        assert RunMixin is not None

    def test_mixin_has_required_methods(self):
        from tod.gui.run_mixin import RunMixin
        methods = ["_on_run", "_validate_params"]
        for name in methods:
            assert hasattr(RunMixin, name), f"RunMixin missing method: {name}"


class TestMainWindowInheritsRunMixin:
    def test_main_window_inherits_run_mixin(self):
        from tod.gui.run_mixin import RunMixin
        try:
            from tod.gui.main_window import MainWindow
        except ImportError as exc:
            pytest.skip(f"MainWindow dependencies unavailable: {exc}")
        assert issubclass(MainWindow, RunMixin)


class TestRunMixinChipExpansion:
    def test_halo_north_south_selection_becomes_one_combined_job(self):
        from tod.gui.run_mixin import RunMixin

        class Harness(RunMixin):
            pass

        harness = Harness()
        harness._current_script = ScriptEntry(
            module="halo",
            name="generate_halo_family",
            description="生成 Halo 轨道族",
            script_path="tod/generates/cr3bp/halo/generate_halo_family.py",
            cli_chip_params=[
                CliChipParam("--libration-point", "平动点", {"L1": "L1", "L2": "L2"}),
                CliChipParam("--halo-class", "Halo 类别", {"北族 (Class I)": "0", "南族 (Class II)": "1"}),
            ],
        )

        combinations = harness._expand_combinations(
            ["--method", "pseudo_arclength"],
            {"libration_point": ["L1"], "halo_class": ["0", "1"]},
        )

        assert combinations == [["--method", "pseudo_arclength", "--libration-point", "L1", "--branches", "both", "--method", "pseudo_arclength"]]

    def test_halo_north_south_selection_combines_per_libration_point(self):
        from tod.gui.run_mixin import RunMixin

        class Harness(RunMixin):
            pass

        harness = Harness()
        harness._current_script = ScriptEntry(
            module="halo",
            name="generate_halo_family",
            description="生成 Halo 轨道族",
            script_path="tod/generates/cr3bp/halo/generate_halo_family.py",
            cli_chip_params=[
                CliChipParam("--libration-point", "平动点", {"L1": "L1", "L2": "L2"}),
                CliChipParam("--halo-class", "Halo 类别", {"北族 (Class I)": "0", "南族 (Class II)": "1"}),
            ],
        )

        combinations = harness._expand_combinations([], {"libration_point": ["L1", "L2"], "halo_class": ["0", "1"]})

        assert combinations == [
            ["--libration-point", "L1", "--branches", "both", "--method", "pseudo_arclength"],
            ["--libration-point", "L2", "--branches", "both", "--method", "pseudo_arclength"],
        ]


class TestRunMixinValidation:
    def test_required_text_cli_param_rejects_blank_value(self):
        from tod.gui.run_mixin import RunMixin

        class FakeLineEdit:
            def text(self):
                return ""

            def setFocus(self):
                pass

        class Harness(RunMixin):
            pass

        widget = FakeLineEdit()
        harness = Harness()
        harness._cli_widgets = {"--reference-epoch": widget}
        harness._find_cli_param = MagicMock(
            return_value=CliParam(
                "--reference-epoch",
                "参考历元",
                "str",
                required=True,
            )
        )

        with (
            patch("tod.gui.run_mixin.QLineEdit", FakeLineEdit),
            patch("tod.gui.run_mixin.QMessageBox.warning") as warning,
        ):
            assert harness._validate_params() is False

        warning.assert_called_once()
        assert warning.call_args.args[2].startswith("脚本需要参数 '参考历元'")
