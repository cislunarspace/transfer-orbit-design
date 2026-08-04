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
        self.setFont(QFont("Consolas", 9))

    def append_log(self, message: str) -> None:
        """追加带时间戳的日志消息。"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.appendPlainText(f"[{timestamp}] {message}")
