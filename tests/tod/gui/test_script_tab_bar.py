"""ScriptTabBar — 多脚本 Tab 管理器的接口与行为测试。"""

import pytest

from tod.gui.script_registry import ScriptEntry


def _make_entry(name: str = "Test Script", script_path: str = "tod/test/script.py") -> ScriptEntry:
    return ScriptEntry(
        module="test",
        name=name,
        description="Test description",
        script_path=script_path,
    )


@pytest.fixture
def qapp_fixture():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    return app


class TestScriptTabBarOpenScript:
    def test_open_new_script_creates_tab(self, qapp_fixture, tmp_path):
        from tod.gui.script_tab_bar import ScriptTabBar
        from tod.gui.script_tab_widget import ScriptTabWidget

        bar = ScriptTabBar(files=[], repo_root=tmp_path, gui_defaults={}, theme_mode="system")
        entry = _make_entry()

        widget = bar.open_script(entry)

        assert isinstance(widget, ScriptTabWidget)
        assert bar._tab_bar.count() == 1
        assert bar._tab_bar.tabText(0) == "Test Script"

    def test_open_same_script_reuses_tab(self, qapp_fixture, tmp_path):
        from tod.gui.script_tab_bar import ScriptTabBar

        bar = ScriptTabBar(files=[], repo_root=tmp_path, gui_defaults={}, theme_mode="system")
        entry = _make_entry()

        w1 = bar.open_script(entry)
        w2 = bar.open_script(entry)

        assert w1 is w2
        assert bar._tab_bar.count() == 1

    def test_open_different_scripts_creates_multiple_tabs(self, qapp_fixture, tmp_path):
        from tod.gui.script_tab_bar import ScriptTabBar

        bar = ScriptTabBar(files=[], repo_root=tmp_path, gui_defaults={}, theme_mode="system")
        e1 = _make_entry("Script A", "tod/test/a.py")
        e2 = _make_entry("Script B", "tod/test/b.py")

        bar.open_script(e1)
        bar.open_script(e2)

        assert bar._tab_bar.count() == 2

    def test_tab_tooltip_shows_script_path(self, qapp_fixture, tmp_path):
        from tod.gui.script_tab_bar import ScriptTabBar

        bar = ScriptTabBar(files=[], repo_root=tmp_path, gui_defaults={}, theme_mode="system")
        entry = _make_entry("Test", "tod/generates/test.py")

        bar.open_script(entry)

        assert bar._tab_bar.tabToolTip(0) == "tod/generates/test.py"


class TestScriptTabBarClose:
    def test_close_tab_removes_tab(self, qapp_fixture, tmp_path):
        from tod.gui.script_tab_bar import ScriptTabBar

        bar = ScriptTabBar(files=[], repo_root=tmp_path, gui_defaults={}, theme_mode="system")
        bar.open_script(_make_entry("A", "tod/a.py"))
        bar.open_script(_make_entry("B", "tod/b.py"))

        bar.close_tab(0)

        assert bar._tab_bar.count() == 1

    def test_close_all_removes_all_tabs(self, qapp_fixture, tmp_path):
        from tod.gui.script_tab_bar import ScriptTabBar

        bar = ScriptTabBar(files=[], repo_root=tmp_path, gui_defaults={}, theme_mode="system")
        bar.open_script(_make_entry("A", "tod/a.py"))
        bar.open_script(_make_entry("B", "tod/b.py"))

        bar.close_all()

        assert bar._tab_bar.count() == 0

    def test_close_others_keeps_specified_tab(self, qapp_fixture, tmp_path):
        from tod.gui.script_tab_bar import ScriptTabBar

        bar = ScriptTabBar(files=[], repo_root=tmp_path, gui_defaults={}, theme_mode="system")
        bar.open_script(_make_entry("A", "tod/a.py"))
        bar.open_script(_make_entry("B", "tod/b.py"))
        bar.open_script(_make_entry("C", "tod/c.py"))

        bar.close_others(1)

        assert bar._tab_bar.count() == 1
        assert bar._tab_bar.tabText(0) == "B"

    def test_close_all_shows_placeholder(self, qapp_fixture, tmp_path):
        from tod.gui.script_tab_bar import ScriptTabBar

        bar = ScriptTabBar(files=[], repo_root=tmp_path, gui_defaults={}, theme_mode="system")
        bar.open_script(_make_entry())

        bar.close_all()

        # Stacked widget 应该显示空白占位
        assert bar._stack.currentWidget() is bar._empty_placeholder


class TestScriptTabBarSwitching:
    def test_tab_switched_signal_emitted(self, qapp_fixture, tmp_path):
        from tod.gui.script_tab_bar import ScriptTabBar

        bar = ScriptTabBar(files=[], repo_root=tmp_path, gui_defaults={}, theme_mode="system")
        e1 = _make_entry("A", "tod/a.py")
        e2 = _make_entry("B", "tod/b.py")

        emitted = []
        bar.tab_switched.connect(lambda e: emitted.append(e.name))

        bar.open_script(e1)
        bar.open_script(e2)

        # 切换到第一个 tab
        bar._tab_bar.setCurrentIndex(0)

        assert "A" in emitted
        assert "B" in emitted

    def test_current_entry_returns_active_script(self, qapp_fixture, tmp_path):
        from tod.gui.script_tab_bar import ScriptTabBar

        bar = ScriptTabBar(files=[], repo_root=tmp_path, gui_defaults={}, theme_mode="system")
        e1 = _make_entry("A", "tod/a.py")
        e2 = _make_entry("B", "tod/b.py")

        bar.open_script(e1)
        bar.open_script(e2)

        assert bar.current_entry() is e2

        bar._tab_bar.setCurrentIndex(0)
        assert bar.current_entry() is e1

    def test_current_widget_returns_correct_widget(self, qapp_fixture, tmp_path):
        from tod.gui.script_tab_bar import ScriptTabBar

        bar = ScriptTabBar(files=[], repo_root=tmp_path, gui_defaults={}, theme_mode="system")
        e1 = _make_entry("A", "tod/a.py")
        e2 = _make_entry("B", "tod/b.py")

        w1 = bar.open_script(e1)
        w2 = bar.open_script(e2)

        assert bar.current_widget() is w2

        bar._tab_bar.setCurrentIndex(0)
        assert bar.current_widget() is w1

    def test_current_entry_returns_none_when_empty(self, qapp_fixture, tmp_path):
        from tod.gui.script_tab_bar import ScriptTabBar

        bar = ScriptTabBar(files=[], repo_root=tmp_path, gui_defaults={}, theme_mode="system")
        assert bar.current_entry() is None


class TestScriptTabBarReopen:
    def test_reopen_activates_existing_tab(self, qapp_fixture, tmp_path):
        from tod.gui.script_tab_bar import ScriptTabBar

        bar = ScriptTabBar(files=[], repo_root=tmp_path, gui_defaults={}, theme_mode="system")
        e1 = _make_entry("A", "tod/a.py")
        e2 = _make_entry("B", "tod/b.py")

        bar.open_script(e1)
        bar.open_script(e2)
        assert bar._tab_bar.currentIndex() == 1

        # 重新打开 e1 应切换到 tab 0
        bar.open_script(e1)
        assert bar._tab_bar.currentIndex() == 0


class TestScriptTabBarForwardedSignals:
    def test_run_requested_forwarded(self, qapp_fixture, tmp_path):
        from tod.gui.script_tab_bar import ScriptTabBar

        bar = ScriptTabBar(files=[], repo_root=tmp_path, gui_defaults={}, theme_mode="system")
        entry = _make_entry()
        widget = bar.open_script(entry)

        emitted = []
        bar.run_requested.connect(lambda w: emitted.append(w))
        widget.run_requested.emit()

        assert len(emitted) == 1
        assert emitted[0] is widget

    def test_defaults_changed_forwarded(self, qapp_fixture, tmp_path):
        from tod.gui.script_tab_bar import ScriptTabBar

        bar = ScriptTabBar(files=[], repo_root=tmp_path, gui_defaults={}, theme_mode="system")
        entry = _make_entry()
        widget = bar.open_script(entry)

        emitted = []
        bar.defaults_changed.connect(lambda: emitted.append(True))
        widget.defaults_changed.emit()

        assert len(emitted) == 1


class TestScriptTabBarMove:
    def test_move_tab_to_leftmost(self, qapp_fixture, tmp_path):
        from tod.gui.script_tab_bar import ScriptTabBar

        bar = ScriptTabBar(files=[], repo_root=tmp_path, gui_defaults={}, theme_mode="system")
        bar.open_script(_make_entry("A", "tod/a.py"))
        bar.open_script(_make_entry("B", "tod/b.py"))
        bar.open_script(_make_entry("C", "tod/c.py"))

        # 移动 C (index 2) 到最左
        bar._move_tab(2, 0)

        assert bar._tab_bar.tabText(0) == "C"
        assert bar._tab_bar.tabText(1) == "A"
        assert bar._tab_bar.tabText(2) == "B"
