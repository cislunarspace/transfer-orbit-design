"""job_panel_mixin — Job 面板 Mixin 的接口测试。"""


class TestJobPanelMixinImportable:
    def test_mixin_importable(self):
        from tod.gui.job_panel_mixin import JobPanelMixin
        assert JobPanelMixin is not None

    def test_mixin_has_required_methods(self):
        from tod.gui.job_panel_mixin import JobPanelMixin
        methods = [
            "_build_job_panel",
            "_on_job_started",
            "_on_job_output",
            "_on_job_finished",
            "_on_job_error",
            "_on_job_card_clicked",
            "_on_stop_current",
            "_on_stop_job_requested",
            "_confirm_and_stop",
            "_on_output_tab_close",
            "_clear_completed_jobs",
            "_update_job_count",
        ]
        for name in methods:
            assert hasattr(JobPanelMixin, name), f"JobPanelMixin missing method: {name}"


class TestMainWindowInheritsJobPanelMixin:
    def test_main_window_inherits_job_panel_mixin(self):
        from tod.gui.job_panel_mixin import JobPanelMixin
        from tod.gui.main_window import MainWindow
        assert issubclass(MainWindow, JobPanelMixin)
