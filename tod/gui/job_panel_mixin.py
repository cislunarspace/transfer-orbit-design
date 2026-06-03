"""PyQt6 图形界面组件。

本模块为 Transfer Orbit Design 的脚本化工作流提供辅助类型、函数或入口。
"""


from __future__ import annotations

import time
from typing import TYPE_CHECKING, cast

from PyQt6.QtCore import QCoreApplication, Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from tod.gui.job_manager import JobManager
from tod.gui.job_status import DispatchResult, JobStatus
from tod.gui.output_panel import JobCard, StructuredOutputWidget

if TYPE_CHECKING:
    from tod.gui.script_registry import ScriptEntry


class JobPanelMixin:
    """提供 Job 面板构建和生命周期管理方法，由 MainWindow 通过多重继承混入。"""

    _status_bar: QStatusBar
    _job_outputs: dict[str, StructuredOutputWidget]
    _job_cards: dict[str, JobCard]
    _job_manager: JobManager
    _has_jobs: bool
    _current_script: ScriptEntry | None
    _run_btn: QPushButton

    def _build_job_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # 顶部：标题 + Clear All Completed
        header = QHBoxLayout()
        self._job_count_label = QLabel("Jobs")
        self._job_count_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        header.addWidget(self._job_count_label)
        header.addStretch()
        self._clear_completed_btn = QPushButton(QCoreApplication.translate("JobPanelMixin", "清除已完成"))
        self._clear_completed_btn.setToolTip(QCoreApplication.translate("JobPanelMixin", "清除所有已完成的任务"))
        self._clear_completed_btn.setStyleSheet(
            "QPushButton { padding: 2px 8px; font-size: 11px; }"
        )
        self._clear_completed_btn.clicked.connect(self._clear_completed_jobs)
        header.addWidget(self._clear_completed_btn)
        layout.addLayout(header)

        # 任务卡片列表
        self._job_scroll = QScrollArea()
        self._job_scroll.setWidgetResizable(True)
        self._job_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._job_scroll.setMaximumHeight(200)
        self._job_scroll.setMinimumHeight(60)

        self._job_cards_container = QWidget()
        self._job_cards_layout = QVBoxLayout(self._job_cards_container)
        self._job_cards_layout.setContentsMargins(0, 0, 0, 0)
        self._job_cards_layout.setSpacing(4)
        self._job_cards_layout.addStretch()
        self._job_scroll.setWidget(self._job_cards_container)
        layout.addWidget(self._job_scroll)

        # 输出 Tab 面板
        self._output_tabs = QTabWidget()
        self._output_tabs.setTabsClosable(True)
        self._output_tabs.tabCloseRequested.connect(self._on_output_tab_close)

        # 空状态占位
        self._empty_label = QLabel("No active jobs.\nSelect a script and click Run.")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet("color: #666; font-size: 12px; padding: 40px;")
        self._output_tabs.addTab(self._empty_label, "(empty)")

        layout.addWidget(self._output_tabs, stretch=1)
        return panel

    # ── 槽：任务生命周期 ───────────────────────────────────

    def _on_job_started(self, job_id: str, name: str) -> None:
        if not job_id:
            return

        # 移除空状态占位
        if not self._has_jobs:
            self._output_tabs.clear()
            self._has_jobs = True

        # 创建输出面板
        output_widget = StructuredOutputWidget()
        output_widget.status_message.connect(
            lambda msg: self._status_bar.showMessage(msg, 5000)
        )
        self._job_outputs[job_id] = output_widget
        tab_idx = self._output_tabs.addTab(output_widget, name)
        self._output_tabs.setCurrentIndex(tab_idx)

        # 创建 Job Card
        card = JobCard(job_id, name)
        card.clicked.connect(self._on_job_card_clicked)
        card.stop_requested.connect(self._on_stop_job_requested)
        self._job_cards[job_id] = card
        # 插入到 stretch 之前
        self._job_cards_layout.insertWidget(
            self._job_cards_layout.count() - 1, card
        )

        self._update_job_count()

    def _on_job_output(self, job_id: str, text: str, stream: str) -> None:
        output = self._job_outputs.get(job_id)
        if output:
            output.append_output(text, stream)

    def _on_job_finished(self, result: DispatchResult) -> None:
        card = self._job_cards.get(result.job_id)
        if card:
            card.set_status(result.status)

        # 任务栏闪烁通知（仅 macOS 支持）
        from PyQt6.QtWidgets import QApplication
        import platform
        app = QApplication.instance()
        if app and platform.system() == "Darwin":
            app.alert(self)  # type: ignore[attr-defined]

        # 状态栏详细消息
        if result.exit_code == 0:
            self._status_bar.showMessage(QCoreApplication.translate("JobPanelMixin", "脚本 '{}' 完成 (exit code: 0)").format(result.script_name), 5000)
        else:
            self._status_bar.showMessage(
                QCoreApplication.translate("JobPanelMixin", "脚本 '{}' 失败 (exit code: {})").format(result.script_name, result.exit_code), 8000
            )

        # 在输出面板追加结束信息
        output = self._job_outputs.get(result.job_id)
        if output:
            banner = f"\n{'='*60}\n[{QCoreApplication.translate("JobPanelMixin", '进程结束')}] exit code: {result.exit_code}\n{'='*60}\n"
            output.append_output(banner, "stdout")
            output.set_finished()

        self._update_job_count()

    def _on_job_error(self, result: DispatchResult) -> None:
        if not result.job_id:
            # 全局错误（如达到并发上限）
            self._status_bar.showMessage(result.error_message)
            return

        card = self._job_cards.get(result.job_id)
        if card:
            card.set_status(result.status)

        output = self._job_outputs.get(result.job_id)
        if output:
            output.append_output(f"\n[ERROR] {result.error_message}\n", "stderr")

        self._update_job_count()

    def _on_job_card_clicked(self, job_id: str) -> None:
        """双击 JobCard 切换到对应输出 tab。"""
        output = self._job_outputs.get(job_id)
        if output:
            idx = self._output_tabs.indexOf(output)
            if idx >= 0:
                self._output_tabs.setCurrentIndex(idx)

    def _on_stop_current(self) -> None:
        """快捷键停止当前查看的 job。"""
        current_widget = self._output_tabs.currentWidget()
        for job_id, widget in self._job_outputs.items():
            if widget is current_widget:
                self._confirm_and_stop(job_id)
                break

    def _on_stop_job_requested(self, job_id: str) -> None:
        """JobCard 停止按钮 — 长时间运行的作业需要确认。"""
        self._confirm_and_stop(job_id)

    def _confirm_and_stop(self, job_id: str) -> None:
        """停止作业，运行超过 60 秒时弹出确认。"""
        job = self._job_manager.get_job(job_id)
        if job is None:
            return
        elapsed = time.time() - job.started_at
        if elapsed > 60:
            reply = QMessageBox.question(
                cast(QWidget, self),
                QCoreApplication.translate("JobPanelMixin", "确认停止"),
                QCoreApplication.translate("JobPanelMixin", "脚本 '{}' 已运行 {} 秒。\n确定停止？").format(job.script_entry.name, int(elapsed)),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        self._job_manager.stop_job(job_id)

    def _on_output_tab_close(self, index: int) -> None:
        """关闭输出 tab。"""
        widget = self._output_tabs.widget(index)
        # 找到对应的 job_id
        job_id_to_remove = None
        for job_id, w in self._job_outputs.items():
            if w is widget:
                job_id_to_remove = job_id
                break

        if job_id_to_remove:
            # 如果 job 还在运行，先确认
            job = self._job_manager.get_job(job_id_to_remove)
            if job and job.status == JobStatus.RUNNING:
                reply = QMessageBox.question(
                    cast(QWidget, self),
                    QCoreApplication.translate("JobPanelMixin", "确认关闭"),
                    QCoreApplication.translate("JobPanelMixin", "脚本 '{}' 正在运行。\n停止并关闭？").format(job.script_entry.name),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if reply != QMessageBox.StandardButton.Yes:
                    return
                self._job_manager.stop_job(job_id_to_remove)
            del self._job_outputs[job_id_to_remove]

        self._output_tabs.removeTab(index)

        # 如果没有 tab 了，恢复空状态
        if self._output_tabs.count() == 0:
            self._output_tabs.addTab(self._empty_label, "(empty)")
            self._has_jobs = False

    def _clear_completed_jobs(self) -> None:
        """清除所有已完成的 job card 和对应的输出 tab。"""
        completed_ids = [
            jid
            for jid, card in self._job_cards.items()
            if not card.is_running
        ]
        for jid in completed_ids:
            # 移除 card
            card = self._job_cards.pop(jid, None)
            if card:
                self._job_cards_layout.removeWidget(card)
                card.deleteLater()

            # 移除输出 tab
            output = self._job_outputs.pop(jid, None)
            if output:
                idx = self._output_tabs.indexOf(output)
                if idx >= 0:
                    self._output_tabs.removeTab(idx)

        if self._output_tabs.count() == 0:
            self._output_tabs.addTab(self._empty_label, "(empty)")
            self._has_jobs = False

        self._update_job_count()

    _RUN_STYLE_READY = (
        "QPushButton {"
        "  padding: 8px 24px;"
        "  font-weight: bold;"
        "  background-color: #0e639c;"
        "  color: white;"
        "  border: none;"
        "  border-radius: 4px;"
        "}"
        "QPushButton:hover { background-color: #1177bb; }"
        "QPushButton:disabled { background-color: #3c3c3c; color: #888; }"
    )
    _RUN_STYLE_FULL = (
        "QPushButton {"
        "  padding: 8px 24px;"
        "  font-weight: bold;"
        "  background-color: #b8860b;"
        "  color: white;"
        "  border: none;"
        "  border-radius: 4px;"
        "}"
        "QPushButton:hover { background-color: #cc9a1a; }"
        "QPushButton:disabled { background-color: #3c3c3c; color: #888; }"
    )

    def _update_job_count(self) -> None:
        running = sum(1 for c in self._job_cards.values() if c.is_running)
        total = len(self._job_cards)
        if total == 0:
            self._job_count_label.setText("Jobs")
        else:
            self._job_count_label.setText(f"Jobs ({running} running, {total} total)")

        self._status_bar.showMessage(
            f"{running} running, {total} total"
            if running > 0
            else "Ready"
        )

        # 更新运行按钮状态
        if self._current_script is not None:
            if running >= JobManager.MAX_CONCURRENT:
                self._run_btn.setText(QCoreApplication.translate("JobPanelMixin", "已达上限 ({})").format(JobManager.MAX_CONCURRENT))
                self._run_btn.setStyleSheet(self._RUN_STYLE_FULL)
                self._run_btn.setEnabled(True)  # 仍可点击以显示错误
            else:
                self._run_btn.setText(QCoreApplication.translate("JobPanelMixin", "运行"))
                self._run_btn.setStyleSheet(self._RUN_STYLE_READY)
                self._run_btn.setEnabled(True)
