"""theme_utils — 主题检测与解析函数的单元测试。"""

from unittest.mock import patch

from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QApplication


def _qapp():
    """确保 QApplication 实例存在（测试环境中可能未创建）。"""
    app = QApplication.instance()
    if app is None:
        return QApplication([])
    return app


class TestIsSystemDark:
    def test_light_palette_returns_false(self):
        _qapp()
        from tod.gui.theme_utils import is_system_dark

        mock_color = QColor(255, 255, 255)  # white → high luminance
        with patch(
            "tod.gui.theme_utils._get_palette_window_color",
            return_value=mock_color,
        ):
            assert is_system_dark() is False

    def test_dark_palette_returns_true(self):
        _qapp()
        from tod.gui.theme_utils import is_system_dark

        mock_color = QColor(30, 30, 30)  # dark → low luminance
        with patch(
            "tod.gui.theme_utils._get_palette_window_color",
            return_value=mock_color,
        ):
            assert is_system_dark() is True


class TestResolveTheme:
    def test_system_mode_returns_light(self):
        from tod.gui.theme_utils import resolve_theme

        with patch("tod.gui.theme_utils.is_system_dark", return_value=False):
            assert resolve_theme("system") == "light"

    def test_system_mode_returns_dark(self):
        from tod.gui.theme_utils import resolve_theme

        with patch("tod.gui.theme_utils.is_system_dark", return_value=True):
            assert resolve_theme("system") == "dark"

    def test_explicit_light(self):
        from tod.gui.theme_utils import resolve_theme

        assert resolve_theme("light") == "light"

    def test_explicit_dark(self):
        from tod.gui.theme_utils import resolve_theme

        assert resolve_theme("dark") == "dark"


class TestGetThemeStylesheet:
    def test_returns_string(self):
        from tod.gui.theme_utils import get_theme_stylesheet

        with patch("tod.gui.theme_utils.resolve_theme", return_value="light"):
            result = get_theme_stylesheet()
            assert isinstance(result, str)
