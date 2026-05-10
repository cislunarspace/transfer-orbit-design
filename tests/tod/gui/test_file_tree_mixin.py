"""file_tree_mixin — 文件浏览器 Mixin 的接口测试。"""


def _qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        return QApplication([])
    return app


class TestFileTreeMixinImportable:
    def test_mixin_importable(self):
        from tod.gui.file_tree_mixin import FileTreeMixin
        assert FileTreeMixin is not None

    def test_mixin_has_required_methods(self):
        from tod.gui.file_tree_mixin import FileTreeMixin
        methods = [
            "_build_file_browser_tab",
            "_on_copy_abs",
            "_on_copy_rel",
            "_on_reveal_in_file_manager",
            "_on_delete_files",
            "_update_file_toolbar_state",
            "_on_file_tree_context_menu",
            "_refresh_files",
            "_rebuild_file_tree",
            "_highlight_category",
        ]
        for name in methods:
            assert hasattr(FileTreeMixin, name), f"FileTreeMixin missing method: {name}"


class TestMainWindowStillHasFileTreeMethods:
    def test_main_window_inherits_file_tree_mixin(self):
        from tod.gui.file_tree_mixin import FileTreeMixin
        from tod.gui.main_window import MainWindow
        assert issubclass(MainWindow, FileTreeMixin)
