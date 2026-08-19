"""日志面板 -- 结构化日志输出。"""

from __future__ import annotations

from datetime import datetime

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QPlainTextEdit


class LogPanel(QPlainTextEdit):
    """带时间戳的只读日志面板。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        # 等宽字族便于对齐时间戳；字号跟随全局基准（界面设置可调），不再偏小
        font = QFont("Consolas")
        font.setPointSize(self.font().pointSize())
        self.setFont(font)

    def append_log(self, message: str) -> None:
        """追加带时间戳的日志消息。"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.appendPlainText(f"[{timestamp}] {message}")
