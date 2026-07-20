"""PyQt6 图形界面组件。

本模块为 Transfer Orbit Design 的脚本化工作流提供辅助类型、函数或入口。
"""


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


# ── 运行按钮样式（集中维护，ScriptParamPanel / JobPanelMixin 共用） ──
# 颜色取双主题可读的中性值：按钮实底白字在亮/暗背景下均成立，
# disabled 用半透明灰，避免暗色专属硬编码。
RUN_BTN_STYLE_READY = (
    "QPushButton {"
    "  padding: 8px 24px;"
    "  font-weight: bold;"
    "  background-color: #0078d4;"
    "  color: white;"
    "  border: none;"
    "  border-radius: 4px;"
    "}"
    "QPushButton:hover { background-color: #106ebe; }"
    "QPushButton:pressed { background-color: #005a9e; }"
    "QPushButton:disabled { background-color: rgba(128,128,128,0.5); color: white; }"
)
RUN_BTN_STYLE_FULL = (
    "QPushButton {"
    "  padding: 8px 24px;"
    "  font-weight: bold;"
    "  background-color: #ca5010;"
    "  color: white;"
    "  border: none;"
    "  border-radius: 4px;"
    "}"
    "QPushButton:hover { background-color: #da6210; }"
    "QPushButton:pressed { background-color: #a8420c; }"
    "QPushButton:disabled { background-color: rgba(128,128,128,0.5); color: white; }"
)
