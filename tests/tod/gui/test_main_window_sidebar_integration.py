# pyright: reportArgumentType=false, reportOptionalMemberAccess=false, reportAttributeAccessIssue=false, reportGeneralTypeIssues=false
"""MainWindow + SidebarWidget 集成测试（issue #63）。"""

import pytest


class TestMainWindowSidebarIntegration:
    """Tests for sidebar tree integration into MainWindow."""

    def test_main_window_has_sidebar_widget_not_buttons(self):
        """MainWindow should use SidebarWidget instead of button list."""
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication([])
        from tod.gui.main_window import MainWindow

        window = MainWindow(repo_root=".")
        sidebar = window._left_splitter.widget(0)

        # SidebarWidget is a container with search + tree
        from tod.gui.sidebar_widget import SidebarWidget
        assert isinstance(sidebar, SidebarWidget), (
            f"Expected SidebarWidget, got {type(sidebar).__name__}"
        )

    def test_sidebar_script_click_triggers_script_selected(self):
        """Clicking a script node in sidebar should trigger _on_script_selected."""
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication([])
        from tod.gui.main_window import MainWindow
        from tod.gui.script_registry import ScriptEntry
        from tod.gui.script_tree import TreeNode

        window = MainWindow(repo_root=".")
        selected: list[ScriptEntry] = []

        # Find the sidebar and its tree
        sidebar = window._left_splitter.widget(0)
        tree = sidebar._tree

        # Create a mock ScriptEntry for testing
        mock_entry = ScriptEntry("dro", "Test Script", "Test description", "tod/test/script.py")
        mock_script_node = TreeNode(
            name="test_script",
            path="tod/test/script.py",
            node_type="script",
            color="#4A90D9",
            script_entry=mock_entry,
        )

        # Patch the tree's callback directly
        original_callback = tree._script_selected_callback
        tree._script_selected_callback = selected.append

        # Create a mock item with the mock node
        from PyQt6.QtWidgets import QTreeWidgetItem
        mock_item = QTreeWidgetItem()
        mock_item.setData(0, tree._NODE_ROLE, mock_script_node)
        mock_item.setData(0, tree._SCRIPT_ROLE, mock_entry)

        # Simulate clicking on the script item
        tree.itemClicked.emit(mock_item, 0)

        # Restore original callback
        tree._script_selected_callback = original_callback

        # Should have selected the mock entry
        assert len(selected) == 1, (
            f"Expected 1 script selected, got {len(selected)}"
        )
        assert selected[0] is mock_entry

    def test_script_selection_switches_right_tabs_to_script_info(self, tmp_path):
        """Selecting a script should leave the Files tab and show Script Info."""
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication([])
        from tod.gui.main_window import MainWindow
        from tod.gui.script_registry import ScriptEntry

        window = MainWindow(repo_root=str(tmp_path))
        tabs = window._right_tabs
        assert tabs is not None

        files_idx = next(
            i for i in range(tabs.count()) if tabs.tabText(i) == "Files"
        )
        script_info_idx = next(
            i for i in range(tabs.count()) if tabs.tabText(i) in {"Script Info", "脚本信息"}
        )
        tabs.setCurrentIndex(files_idx)

        entry = ScriptEntry(
            "dro",
            "Test Script",
            "Test description",
            "tod/test/script.py",
        )
        window._on_script_selected(entry)

        assert tabs.currentIndex() == script_info_idx
        assert tabs.tabText(tabs.currentIndex()) in {"Script Info", "脚本信息"}


class TestMainWindowThemeSwitching:
    """Tests for theme switching with sidebar rebuild."""

    def test_theme_switch_rebuilds_sidebar(self):
        """Theme switch should rebuild the sidebar widget."""
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication([])
        from tod.gui.main_window import MainWindow
        from tod.gui.sidebar_widget import SidebarWidget

        window = MainWindow(repo_root=".")
        old_sidebar = window._left_splitter.widget(0)

        # Trigger theme change
        window._current_theme_mode = "light"
        window._on_theme_changed()

        new_sidebar = window._left_splitter.widget(0)

        assert isinstance(new_sidebar, SidebarWidget)
        assert new_sidebar is not old_sidebar, (
            "Sidebar should be rebuilt on theme change"
        )


class TestMainWindowPreservedFeatures:
    """Tests that preserved features still work after integration."""

    def test_keyboard_shortcuts_exist(self):
        """MainWindow should have Ctrl+R and Ctrl+Shift+X shortcuts."""
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication([])
        from tod.gui.main_window import MainWindow

        window = MainWindow(repo_root=".")

        # Check shortcuts are connected by finding them in children
        shortcuts = window.findChildren(
            __import__("PyQt6.QtGui", fromlist=["QShortcut"]).QShortcut
        )
        shortcut_keys = {s.key().toString() for s in shortcuts}

        assert "Ctrl+R" in shortcut_keys or "ctrl+r" in shortcut_keys
        assert "Ctrl+Shift+X" in shortcut_keys or "ctrl+shift+x" in shortcut_keys

    def test_toolbar_buttons_exist(self):
        """MainWindow should have refresh and settings toolbar buttons."""
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication([])
        from tod.gui.main_window import MainWindow

        window = MainWindow(repo_root=".")

        # Check toolbar exists
        toolbars = window.findChildren(
            __import__("PyQt6.QtWidgets", fromlist=["QToolBar"]).QToolBar
        )
        assert len(toolbars) > 0, "MainWindow should have at least one toolbar"

        # Check toolbar has buttons
        toolbar = toolbars[0]
        buttons = toolbar.findChildren(
            __import__("PyQt6.QtWidgets", fromlist=["QPushButton"]).QPushButton
        )
        button_texts = {b.text() for b in buttons}

        assert button_texts & {"刷新文件", "Refresh Files"}, "Toolbar should have refresh button"
        assert button_texts & {"设置", "Settings"}, "Toolbar should have settings button"
