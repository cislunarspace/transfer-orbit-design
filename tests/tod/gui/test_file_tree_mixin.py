"""file_tree_mixin — 文件浏览器 Mixin 的接口测试。"""

from unittest.mock import MagicMock


class TestFileTreeMixinImportable:
    def test_mixin_importable(self):
        from tod.gui.files.file_tree_mixin import FileTreeMixin
        assert FileTreeMixin is not None

    def test_mixin_has_required_methods(self):
        from tod.gui.files.file_tree_mixin import FileTreeMixin
        methods = [
            "_build_file_browser_tab",
            "_on_copy_abs",
            "_on_copy_rel",
            "_on_reveal_in_file_manager",
            "_on_delete_files",
            "_update_file_toolbar_state",
            "_on_file_tree_context_menu",
            "_rebuild_file_tree",
            "_highlight_category",
        ]
        for name in methods:
            assert hasattr(FileTreeMixin, name), f"FileTreeMixin missing method: {name}"


class TestMainWindowStillHasFileTreeMethods:
    def test_main_window_inherits_file_tree_mixin(self):
        from tod.gui.files.file_tree_mixin import FileTreeMixin
        from tod.gui.main_window import MainWindow
        assert issubclass(MainWindow, FileTreeMixin)


class TestUpdateFileToolbarState:
    def _make_mock_tree(self, selected_paths: list[str | None]) -> MagicMock:
        """创建模拟 QTreeWidget，返回 selectedItems 的 mock。"""
        tree = MagicMock()
        items = []
        for path in selected_paths:
            item = MagicMock()
            item.data.return_value = path
            items.append(item)
        tree.selectedItems.return_value = items
        return tree

    def test_single_selection_enables_reveal_button(self):
        """单选时「打开」按钮应启用。"""
        from tod.gui.files.file_tree_mixin import FileTreeMixin

        mixin = object.__new__(FileTreeMixin)
        mixin._copy_btn = MagicMock()
        mixin._reveal_btn = MagicMock()
        mixin._delete_btn = MagicMock()
        mixin._file_tree = self._make_mock_tree(["/output/dro/family.json"])

        mixin._update_file_toolbar_state()

        # 单选时所有按钮都启用
        mixin._copy_btn.setEnabled.assert_called_with(True)
        mixin._reveal_btn.setEnabled.assert_called_with(True)
        mixin._delete_btn.setEnabled.assert_called_with(True)

    def test_multiple_selection_disables_reveal_button(self):
        """多选时「打开」按钮应禁用，复制和删除仍启用。"""
        from tod.gui.files.file_tree_mixin import FileTreeMixin

        mixin = object.__new__(FileTreeMixin)
        mixin._copy_btn = MagicMock()
        mixin._reveal_btn = MagicMock()
        mixin._delete_btn = MagicMock()
        mixin._file_tree = self._make_mock_tree(["/output/dro/f1.json", "/output/dro/f2.json"])

        mixin._update_file_toolbar_state()

        # 多选时复制和删除启用，打开禁用
        mixin._copy_btn.setEnabled.assert_called_with(True)
        mixin._reveal_btn.setEnabled.assert_called_with(False)
        mixin._delete_btn.setEnabled.assert_called_with(True)

    def test_no_selection_disables_all_buttons(self):
        """无选中时所有按钮都禁用。"""
        from tod.gui.files.file_tree_mixin import FileTreeMixin

        mixin = object.__new__(FileTreeMixin)
        mixin._copy_btn = MagicMock()
        mixin._reveal_btn = MagicMock()
        mixin._delete_btn = MagicMock()
        mixin._file_tree = self._make_mock_tree([])

        mixin._update_file_toolbar_state()

        mixin._copy_btn.setEnabled.assert_called_with(False)
        mixin._reveal_btn.setEnabled.assert_called_with(False)
        mixin._delete_btn.setEnabled.assert_called_with(False)


class TestFileTreeSelectionMode:
    def test_category_folder_flags_should_disable_selection(self):
        """分类文件夹创建后应移除 ItemIsSelectable 标志。"""
        import inspect
        from tod.gui.files.file_tree_mixin import FileTreeMixin

        source = inspect.getsource(FileTreeMixin._rebuild_file_tree)

        # 检查是否有为分类文件夹（cat_item）设置 flags 的代码
        # 正确实现应该在 cat_item 创建后调用 setFlags 移除 ItemIsSelectable
        # 需要检查 cat_item.setFlags 或 cat_item.flags() 相关的代码
        has_cat_flag_modification = (
            "cat_item.setFlags" in source
            or "cat_item.flags()" in source
        )
        assert has_cat_flag_modification, (
            "_rebuild_file_tree should modify cat_item flags to remove ItemIsSelectable"
        )

    def test_file_item_has_selectable_flag(self):
        """文件项创建时应该保留 ItemIsSelectable（默认行为）。"""
        import inspect
        from tod.gui.files.file_tree_mixin import FileTreeMixin

        source = inspect.getsource(FileTreeMixin._rebuild_file_tree)

        # 文件项使用 QTreeWidgetItem(parent, [...]) 创建
        # 不应该修改其 ItemIsSelectable 标志
        assert "QTreeWidgetItem(parent," in source, (
            "_rebuild_file_tree should create file items with QTreeWidgetItem(parent, ...)"
        )


class TestBuildFileBrowserTab:
    def test_file_tree_set_extended_selection_mode(self):
        """_build_file_browser_tab 应调用 setSelectionMode(ExtendedSelection)。"""
        import inspect
        from tod.gui.files.file_tree_mixin import FileTreeMixin

        source = inspect.getsource(FileTreeMixin._build_file_browser_tab)

        # 检查代码中是否设置了 ExtendedSelection 模式
        assert "ExtendedSelection" in source, (
            "_build_file_browser_tab should set selectionMode to ExtendedSelection"
        )
