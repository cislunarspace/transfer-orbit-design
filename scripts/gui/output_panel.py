"""结构化输出面板 — 每个 Job 独立的输出显示，支持 ANSI 清理、时间戳、着色。"""

from __future__ import annotations

import platform
import re
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QTextBrowser,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

# ANSI 转义序列匹配
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")

# 分隔线检测（连续 = 或 -）
_SECTION_RE = re.compile(r"^\s*[=-]{10,}\s*$")

# 进度百分比检测
_PROGRESS_RE = re.compile(r"(\d+)%")

# 最大输出字符数
_MAX_BUFFER = 100_000


def _strip_ansi(text: str) -> str:
    """移除 ANSI 转义序列。"""
    return _ANSI_RE.sub("", text)


def _html_escape(text: str) -> str:
    """转义 HTML 特殊字符。"""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


class StructuredOutputWidget(QWidget):
    """单个 Job 的结构化输出面板：时间戳、着色、自动滚动。"""

    status_message = pyqtSignal(str)  # 向主窗口状态栏发送消息

    def __init__(self, parent=None):
        super().__init__(parent)
        self._start_time = datetime.now()
        self._auto_scroll = True
        self._raw_lines: list[str] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # 工具栏
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(0, 0, 0, 0)

        self._copy_btn = QPushButton("Copy All")
        self._copy_btn.setToolTip("复制全部输出到剪贴板")
        self._copy_btn.clicked.connect(self._copy_all)

        self._save_btn = QPushButton("Save to File")
        self._save_btn.setToolTip("保存输出到文件")
        self._save_btn.clicked.connect(self._save_to_file)

        self._clear_btn = QPushButton("Clear")
        self._clear_btn.setToolTip("清除输出")
        self._clear_btn.clicked.connect(self.clear)

        toolbar.addWidget(self._copy_btn)
        toolbar.addWidget(self._save_btn)
        toolbar.addWidget(self._clear_btn)
        toolbar.addStretch()

        # 已用时间
        self._elapsed_label = QLabel("00:00:00")
        self._elapsed_label.setStyleSheet("color: #888; font-size: 10px;")
        self._elapsed_label.setMinimumWidth(60)
        toolbar.addWidget(self._elapsed_label)

        layout.addLayout(toolbar)

        # 进度条
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setFixedHeight(6)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setStyleSheet(
            "QProgressBar {"
            "  background-color: #333; border: none; border-radius: 3px;"
            "}"
            "QProgressBar::chunk {"
            "  background-color: #0e639c; border-radius: 3px;"
            "}"
        )
        self._progress_bar.hide()
        layout.addWidget(self._progress_bar)

        # 输出文本区域
        self._browser = QTextBrowser()
        self._browser.setReadOnly(True)
        self._browser.setOpenExternalLinks(False)

        # 等宽字体
        font = self._browser.font()
        font.setFamily(
            "Consolas"
            if platform.system() == "Windows"
            else "Menlo"
            if platform.system() == "Darwin"
            else "Monospace"
        )
        font.setPointSize(9)
        self._browser.setFont(font)
        self._browser.setStyleSheet(
            "QTextBrowser {"
            "  background-color: #1e1e1e;"
            "  color: #d4d4d4;"
            "  border: 1px solid #333;"
            "  selection-background-color: #264f78;"
            "}"
        )

        layout.addWidget(self._browser)

        # 追踪滚动位置以实现 "上滚暂停自动滚动"
        self._browser.verticalScrollBar().valueChanged.connect(
            self._on_scroll_changed
        )

        # 已用时间定时器
        self._elapsed_timer = QTimer(self)
        self._elapsed_timer.timeout.connect(self._update_elapsed_label)
        self._elapsed_timer.start(1000)

    def append_output(self, text: str, stream: str) -> None:
        """追加输出文本。stream 为 'stdout' 或 'stderr'。"""
        cleaned = _strip_ansi(text)
        if not cleaned:
            return

        elapsed = datetime.now() - self._start_time
        hours, remainder = divmod(int(elapsed.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        ts = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

        # 逐行处理
        for line in cleaned.splitlines():
            self._raw_lines.append(line)

            # 检测进度行：用 \r 覆盖的行，只保留最新
            if "\r" in line:
                continue

            if _SECTION_RE.match(line):
                html = (
                    f'<div style="color:#888; margin:4px 0;">'
                    f"{_html_escape(line)}"
                    f"</div>"
                )
            elif stream == "stderr":
                html = (
                    f'<span style="color:#f44747;">'
                    f"[{ts}] {_html_escape(line)}"
                    f"</span><br>"
                )
            else:
                # 检测进度百分比
                prog_match = _PROGRESS_RE.search(line)
                if prog_match:
                    pct = int(prog_match.group(1))
                    # 更新进度条
                    self._progress_bar.show()
                    self._progress_bar.setValue(min(pct, 100))
                    html = (
                        f'<span style="color:#dcdcaa;">'
                        f"[{ts}] {_html_escape(line)} ({pct}%)"
                        f"</span><br>"
                    )
                else:
                    html = f"[{_html_escape(ts)}] {_html_escape(line)}<br>"

            self._browser.append(html)

            # 缓冲限制：截断时回退为纯文本（丢失 HTML 着色，但保证内存可控）
            if len(self._browser.toPlainText()) > _MAX_BUFFER:
                # 截断前半部分
                full = self._browser.toPlainText()
                keep = full[_MAX_BUFFER // 2 :]
                self._browser.setPlainText(keep)
                self._browser.moveCursor(
                    self._browser.textCursor().End
                )

        if self._auto_scroll:
            sb = self._browser.verticalScrollBar()
            sb.setValue(sb.maximum())

    def clear(self) -> None:
        self._browser.clear()
        self._raw_lines.clear()

    def _copy_all(self) -> None:
        from PyQt6.QtWidgets import QApplication, QToolTip

        QApplication.clipboard().setText(self._browser.toPlainText())
        # 复制确认提示
        QToolTip.showText(
            self._copy_btn.mapToGlobal(self._copy_btn.rect().center()),
            "已复制！",
            self._copy_btn,
        )
        QTimer.singleShot(1500, QToolTip.hideText)

    def _save_to_file(self) -> None:
        from PyQt6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getSaveFileName(
            self,
            "保存输出",
            f"output_{self._start_time:%Y%m%d_%H%M%S}.log",
            "Log Files (*.log);;All Files (*)",
        )
        if path:
            Path(path).write_text(self._browser.toPlainText(), encoding="utf-8")
            self.status_message.emit(f"输出已保存到 {Path(path).name}")

    def _on_scroll_changed(self, value: int) -> None:
        sb = self._browser.verticalScrollBar()
        # 如果用户手动滚到底部附近，恢复自动滚动
        self._auto_scroll = value >= sb.maximum() - 20

    def _update_elapsed_label(self) -> None:
        elapsed = datetime.now() - self._start_time
        total_secs = int(elapsed.total_seconds())
        h, rem = divmod(total_secs, 3600)
        m, s = divmod(rem, 60)
        self._elapsed_label.setText(f"{h:02d}:{m:02d}:{s:02d}")

    def set_finished(self) -> None:
        """标记作业完成，停止计时并显示最终耗时。"""
        self._elapsed_timer.stop()
        elapsed = datetime.now() - self._start_time
        total_secs = int(elapsed.total_seconds())
        h, rem = divmod(total_secs, 3600)
        m, s = divmod(rem, 60)
        self._elapsed_label.setText(f"完成 {h:02d}:{m:02d}:{s:02d}")
        self._progress_bar.hide()


class JobCard(QWidget):
    """Job 列表中的单个卡片：显示脚本名、状态、运行时间、停止按钮。"""

    clicked = pyqtSignal(str)          # job_id
    stop_requested = pyqtSignal(str)   # job_id

    def __init__(self, job_id: str, script_name: str, parent=None):
        super().__init__(parent)
        self.job_id = job_id
        self._script_name = script_name
        self._is_running = True

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        # 状态徽章
        self._badge = QLabel("●")
        self._badge.setStyleSheet("color: #4ec9b0; font-size: 14px;")
        self._badge.setFixedWidth(16)
        layout.addWidget(self._badge)

        # 脚本名
        self._name_label = QLabel(script_name)
        self._name_label.setStyleSheet("font-weight: bold; font-size: 11px;")
        self._name_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        layout.addWidget(self._name_label)

        # 已运行时间
        self._elapsed_label = QLabel("00:00")
        self._elapsed_label.setStyleSheet("color: #888; font-size: 10px;")
        self._elapsed_label.setMinimumWidth(50)
        layout.addWidget(self._elapsed_label)

        # 停止按钮
        self._stop_btn = QToolButton()
        self._stop_btn.setText("✕")
        self._stop_btn.setToolTip("停止此任务")
        self._stop_btn.setStyleSheet(
            "QToolButton {"
            "  color: #f44747;"
            "  border: none;"
            "  padding: 2px 6px;"
            "  font-size: 12px;"
            "}"
            "QToolButton:hover {"
            "  background-color: #3c1f1f;"
            "  border-radius: 3px;"
            "}"
        )
        self._stop_btn.clicked.connect(lambda: self.stop_requested.emit(self.job_id))
        layout.addWidget(self._stop_btn)

        # 卡片样式
        self.setStyleSheet(
            "JobCard {"
            "  background-color: #252526;"
            "  border: 1px solid #3c3c3c;"
            "  border-radius: 4px;"
            "}"
            "JobCard:hover {"
            "  border-color: #555;"
            "}"
        )
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        # 定时器更新运行时间
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_elapsed)
        self._start_time = datetime.now()
        self._timer.start(1000)

        # 徽章脉动定时器
        self._pulse_timer = QTimer(self)
        self._pulse_timer.timeout.connect(self._toggle_pulse)
        self._pulse_phase = False
        self._pulse_timer.start(1000)

    def mouseDoubleClickEvent(self, event) -> None:
        self.clicked.emit(self.job_id)

    @property
    def is_running(self) -> bool:
        return self._is_running

    def set_status(self, status: str) -> None:
        """设置状态：running / completed / error / killed。"""
        self._is_running = status == "running"
        colors = {
            "running": "#4ec9b0",
            "completed": "#808080",
            "error": "#f44747",
            "killed": "#ce9178",
        }
        color = colors.get(status, "#808080")
        self._badge.setStyleSheet(f"color: {color}; font-size: 14px;")

        self._stop_btn.setVisible(self._is_running)
        if not self._is_running:
            self._timer.stop()
            self._pulse_timer.stop()

    def _toggle_pulse(self) -> None:
        """脉动效果：交替亮/暗绿色。"""
        if not self._is_running:
            return
        self._pulse_phase = not self._pulse_phase
        color = "#4ec9b0" if self._pulse_phase else "#2a7a6a"
        self._badge.setStyleSheet(f"color: {color}; font-size: 14px;")

    def _update_elapsed(self) -> None:
        elapsed = datetime.now() - self._start_time
        total_secs = int(elapsed.total_seconds())
        if total_secs < 3600:
            self._elapsed_label.setText(
                f"{total_secs // 60:02d}:{total_secs % 60:02d}"
            )
        else:
            h, rem = divmod(total_secs, 3600)
            self._elapsed_label.setText(
                f"{h:02d}:{rem // 60:02d}:{rem % 60:02d}"
            )
