"""主题检测与解析工具函数。"""

from __future__ import annotations

from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QApplication

from tod.gui.themes import load_stylesheet


def _get_palette_window_color():
    """获取当前应用调色板的 Window 颜色。"""
    app = QApplication.instance()
    if app is None or not isinstance(app, QGuiApplication):
        return None
    palette = app.palette()
    return palette.color(palette.ColorRole.Window)


def is_system_dark() -> bool:
    """检测系统是否使用暗色模式。"""
    color = _get_palette_window_color()
    if color is None:
        return False
    luminance = 0.299 * color.red() + 0.587 * color.green() + 0.114 * color.blue()
    return luminance < 128


def resolve_theme(mode: str = "system") -> str:
    """根据模式返回实际主题名：light / dark。"""
    if mode == "system":
        return "dark" if is_system_dark() else "light"
    return mode


def get_theme_stylesheet(mode: str = "system") -> str:
    """返回当前主题对应的样式表。"""
    return load_stylesheet(resolve_theme(mode))
