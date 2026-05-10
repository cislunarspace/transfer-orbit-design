"""params_panel_mixin — 参数面板 Mixin 的接口测试。"""


class TestParamsPanelMixinImportable:
    def test_mixin_importable(self):
        from tod.gui.params_panel_mixin import ParamsPanelMixin
        assert ParamsPanelMixin is not None

    def test_mixin_has_required_methods(self):
        from tod.gui.params_panel_mixin import ParamsPanelMixin
        methods = [
            "_rebuild_params_panel",
            "_on_path_mode_changed",
            "_make_cli_widget",
            "_display_widget",
            "_set_widget_std_value",
            "_add_cli_param_row",
            "_connect_param_highlight",
            "_update_param_highlight",
            "_to_standard_unit",
            "_on_unit_changed",
            "_find_cli_param",
            "_setup_conditional_visibility",
            "_on_save_defaults",
            "_on_reset_defaults",
        ]
        for name in methods:
            assert hasattr(ParamsPanelMixin, name), f"ParamsPanelMixin missing method: {name}"


class TestMainWindowInheritsParamsPanelMixin:
    def test_main_window_inherits_params_panel_mixin(self):
        from tod.gui.params_panel_mixin import ParamsPanelMixin
        from tod.gui.main_window import MainWindow
        assert issubclass(MainWindow, ParamsPanelMixin)
