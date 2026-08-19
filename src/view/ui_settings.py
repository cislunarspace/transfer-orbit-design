"""界面设置：字号/主题 + QSettings 持久化 + 全局样式表 + 设置对话框。

照 chart_settings 范式：``UISettings`` dataclass 存可调项，QSettings 持久化；
``apply_ui_settings`` 在启动时（创建主窗口前）把字号与主题应用到 QApplication，
修改重启后生效。全局 QSS 由 ``build_app_stylesheet`` 集中生成——控件颜色不再
散落在各文件的内联 setStyleSheet 里，运行/停止按钮经 objectName
（``runButton``/``stopButton``）挂钩。
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass

#: 可选主题
THEME_OPTIONS: list[str] = ["light", "dark"]
#: 主题在用户界面上的显示名
THEME_LABELS: dict[str, str] = {"light": "浅色", "dark": "深色"}

#: 基准字号可调范围（所有控件字号由此派生，不再有个别小字）
MIN_FONT_SIZE = 8
MAX_FONT_SIZE = 16

#: matplotlib 侧随主题切换的 rcParams（Qt 侧由 QSS 覆盖）
_MPL_THEME_PARAMS: dict[str, dict[str, str]] = {
    "light": {
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "axes.edgecolor": "black",
        "axes.labelcolor": "black",
        "text.color": "black",
        "xtick.color": "black",
        "ytick.color": "black",
    },
    "dark": {
        "figure.facecolor": "#2b2b2b",
        "axes.facecolor": "#2b2b2b",
        "axes.edgecolor": "#888888",
        "axes.labelcolor": "#e8e8e8",
        "text.color": "#e8e8e8",
        "xtick.color": "#c8c8c8",
        "ytick.color": "#c8c8c8",
    },
}


@dataclass
class UISettings:
    """界面外观的可调项。默认值即高可用的浅色主题。"""

    #: 基准字号（pt），控件与图表文字统一由此派生
    font_size: int = 10
    #: 主题：light / dark
    theme: str = "light"


def load_ui_settings(qsettings) -> UISettings:
    """从 QSettings 加载 UISettings；缺失键用默认值，坏值丢弃。

    QSettings ini 格式会把数值读回为 str（如 "10"），显式转换；字号夹在
    [MIN_FONT_SIZE, MAX_FONT_SIZE]，主题不在 THEME_OPTIONS 内回退 light。
    """
    settings = UISettings()
    raw_size = qsettings.value("ui/font_size")
    if raw_size is not None:
        with contextlib.suppress(TypeError, ValueError):
            # 无法解析的值丢弃，用默认
            settings.font_size = min(max(int(raw_size), MIN_FONT_SIZE), MAX_FONT_SIZE)
    raw_theme = qsettings.value("ui/theme")
    if raw_theme in THEME_OPTIONS:
        settings.theme = raw_theme
    return settings


def save_ui_settings(qsettings, settings: UISettings) -> None:
    """把 UISettings 写入 QSettings。"""
    qsettings.setValue("ui/font_size", settings.font_size)
    qsettings.setValue("ui/theme", settings.theme)


def build_app_stylesheet(theme: str) -> str:
    """生成全局 QSS：分隔条、运行/停止按钮为两主题通用；深色另加底色覆盖。

    浅色主题用 Qt 默认底色（白底深色文字），不另设文字颜色——辅助说明文字
    与正文同色，不再用低对比的灰色小字。
    """
    if theme == "dark":
        handle, handle_hover = "#555555", "#888888"
        base = (
            "QWidget { background-color: #2b2b2b; color: #e8e8e8; }"
            "QLineEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox,"
            " QTreeWidget, QAbstractItemView {"
            " background-color: #3a3a3a; color: #e8e8e8; border: 1px solid #555555; }"
            "QPushButton { background-color: #3a3a3a; border: 1px solid #555555;"
            " padding: 4px 8px; }"
            "QPushButton:hover { background-color: #4a4a4a; }"
            "QMenuBar, QMenu { background-color: #2b2b2b; color: #e8e8e8; }"
            "QMenu::item:selected { background-color: #4a4a4a; }"
            "QToolTip { background-color: #3a3a3a; color: #e8e8e8; border: 1px solid #555555; }"
        )
    else:
        handle, handle_hover = "#c8c8c8", "#8f8f8f"
        base = ""
    # 分隔条着色：默认 handle 过细难抓，着色 + hover 加深；按钮经 objectName 挂钩
    return base + (
        f"QSplitter::handle {{ background-color: {handle}; }}"
        f"QSplitter::handle:hover {{ background-color: {handle_hover}; }}"
        "QPushButton#runButton { background-color: #4CAF50; color: white;"
        " font-weight: bold; padding: 6px; border-radius: 4px; }"
        "QPushButton#runButton:hover { background-color: #45a049; }"
        "QPushButton#stopButton { background-color: #d9534f; color: white;"
        " font-weight: bold; padding: 6px; border-radius: 4px; }"
        "QPushButton#stopButton:hover { background-color: #c9302c; }"
    )


def apply_ui_settings(app, settings: UISettings) -> None:
    """把字号与主题应用到 QApplication 与 matplotlib rcParams。

    须在创建主窗口前调用；运行期修改的设置在下次启动经此生效。
    """
    font = app.font()
    font.setPointSize(settings.font_size)
    app.setFont(font)
    app.setStyleSheet(build_app_stylesheet(settings.theme))

    import matplotlib

    matplotlib.rcParams.update(_MPL_THEME_PARAMS[settings.theme])


def ui_settings_dialog(parent, current: UISettings) -> UISettings | None:
    """弹出界面设置对话框，返回新设置；取消返回 None。"""
    from PyQt6.QtWidgets import (
        QComboBox,
        QDialog,
        QDialogButtonBox,
        QFormLayout,
        QLabel,
        QSpinBox,
    )

    dlg = QDialog(parent)
    dlg.setWindowTitle("界面设置")
    form = QFormLayout(dlg)

    font_size = QSpinBox()
    font_size.setRange(MIN_FONT_SIZE, MAX_FONT_SIZE)
    font_size.setValue(current.font_size)
    form.addRow("字体大小", font_size)

    theme = QComboBox()
    for key in THEME_OPTIONS:
        theme.addItem(THEME_LABELS[key], key)
    theme.setCurrentIndex(
        THEME_OPTIONS.index(current.theme) if current.theme in THEME_OPTIONS else 0
    )
    form.addRow("主题", theme)

    note = QLabel("界面设置将在下次启动时生效")
    note.setWordWrap(True)
    form.addRow(note)

    buttons = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
    )
    buttons.accepted.connect(dlg.accept)
    buttons.rejected.connect(dlg.reject)
    form.addRow(buttons)

    if dlg.exec() != QDialog.DialogCode.Accepted:
        return None

    return UISettings(font_size=font_size.value(), theme=theme.currentData())
