"""run_mixin — 运行与验证 Mixin 的接口测试。"""


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
        from tod.gui.main_window import MainWindow
        assert issubclass(MainWindow, RunMixin)
