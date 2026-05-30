"""params_panel_layout_mixin — 参数面板布局 Mixin 的接口测试。"""


class TestParamsPanelLayoutMixinImportable:
    def test_mixin_importable(self):
        from tod.gui.params_panel_layout_mixin import ParamsPanelLayoutMixin
        assert ParamsPanelLayoutMixin is not None

    def test_mixin_has_required_methods(self):
        from tod.gui.params_panel_layout_mixin import ParamsPanelLayoutMixin
        methods = [
            "_rebuild_params_panel",
            "_add_cli_param_row",
            "_add_multi_file_param",
            "_create_config_panel",
            "_on_multi_file_selection_changed",
            "_on_doc_link_clicked",
            "_make_cli_widget",
            "_display_widget",
        ]
        for name in methods:
            assert hasattr(ParamsPanelLayoutMixin, name), f"ParamsPanelLayoutMixin missing method: {name}"


class TestParamsPanelStateMixinImportable:
    def test_mixin_importable(self):
        from tod.gui.params_panel_state_mixin import ParamsPanelStateMixin
        assert ParamsPanelStateMixin is not None

    def test_mixin_has_required_methods(self):
        from tod.gui.params_panel_state_mixin import ParamsPanelStateMixin
        methods = [
            "_on_path_mode_changed",
            "_set_widget_std_value",
            "_to_standard_unit",
            "_on_unit_changed",
            "_find_cli_param",
            "_setup_conditional_visibility",
            "_connect_param_highlight",
            "_update_param_highlight",
            "_on_save_defaults",
            "_on_reset_defaults",
            "_collect_current_param_values",
            "_restore_param_values",
        ]
        for name in methods:
            assert hasattr(ParamsPanelStateMixin, name), f"ParamsPanelStateMixin missing method: {name}"


class TestMainWindowUsesScriptTabBar:
    def test_main_window_has_script_tab_bar(self):
        from PyQt6.QtWidgets import QApplication
        from tod.gui.main_window import MainWindow
        from tod.gui.script_tab_bar import ScriptTabBar

        app = QApplication.instance() or QApplication([])
        window = MainWindow(repo_root=".")
        assert isinstance(window._script_tab_bar, ScriptTabBar)
