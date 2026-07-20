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

from tod.gui.batch import BATCH_AGGREGATE_DISPLAY, BatchAggregate
from tod.gui.batch.batch_summary_card import BatchJobRow, BatchSummaryCard, BatchSummaryViewModel
from tod.gui.i18n import qt_format
from tod.gui.jobs.job_manager import JobManager
from tod.gui.jobs.job_status import JobFinishResult, JobStatus
from tod.gui.jobs.output_panel import JobCard, StructuredOutputWidget
from tod.gui.theme_utils import RUN_BTN_STYLE_FULL, RUN_BTN_STYLE_READY

if TYPE_CHECKING:
    from tod.gui.batch.batch_manager import BatchManager
    from tod.gui.batch import BatchRun
    from tod.scripting import ScriptEntry


class JobPanelMixin:
    """提供 Job 面板构建和生命周期管理方法，由 MainWindow 通过多重继承混入。"""

    _status_bar: QStatusBar
    _job_outputs: dict[str, StructuredOutputWidget]
    _job_cards: dict[str, JobCard]
    _job_manager: JobManager
    _has_jobs: bool
    _current_script: ScriptEntry | None
    _batch_manager: BatchManager
    _batch_cards: dict[str, BatchSummaryCard]

    def _build_job_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # 顶部：标题 + Clear All Completed
        header = QHBoxLayout()
        self._job_count_label = QLabel(QCoreApplication.translate("JobPanelMixin", "任务"))
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

        # 批量运行摘要卡片区
        batches_section = self._build_batches_section()
        layout.addWidget(batches_section)

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
        self._empty_label = QLabel(QCoreApplication.translate("JobPanelMixin", "没有活跃任务。\n请从左侧选择工具并点击运行。"))
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet("color: #888; font-size: 12px; padding: 40px;")
        self._output_tabs.addTab(self._empty_label, "(empty)")

        layout.addWidget(self._output_tabs, stretch=1)
        return panel

    # ── 批量运行摘要卡片区 ─────────────────────────────────

    def _build_batches_section(self) -> QWidget:
        """构建批量运行摘要卡片区（位于 jobs 上方）。"""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        header = QHBoxLayout()
        self._batches_label = QLabel(QCoreApplication.translate("JobPanelMixin", "批量任务"))
        self._batches_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        header.addWidget(self._batches_label)
        header.addStretch()
        layout.addLayout(header)

        self._batch_scroll = QScrollArea()
        self._batch_scroll.setWidgetResizable(True)
        self._batch_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._batch_scroll.setMaximumHeight(200)
        self._batch_scroll.setMinimumHeight(0)

        self._batch_cards_container = QWidget()
        self._batch_cards_layout = QVBoxLayout(self._batch_cards_container)
        self._batch_cards_layout.setContentsMargins(0, 0, 0, 0)
        self._batch_cards_layout.setSpacing(4)
        self._batch_cards_layout.addStretch()
        self._batch_scroll.setWidget(self._batch_cards_container)
        layout.addWidget(self._batch_scroll)

        # 初始隐藏（无 batch 时整个区域不可见）
        container.setVisible(False)
        self._batches_container = container

        return container

    def _build_batch_summary_view_model(
        self, batch_id: str
    ) -> BatchSummaryViewModel | None:
        """从 BatchManager 查询，构造 BatchSummaryViewModel 纯数据快照。

        Returns:
            BatchSummaryViewModel 或 None（batch 不存在或聚合查询失败时）。
        """
        batch: BatchRun | None = self._batch_manager.get_batch(batch_id)
        if batch is None:
            return None
        agg: BatchAggregate | None = self._batch_manager.get_aggregate(batch_id)
        if agg is None:
            return None

        jobs: list[BatchJobRow] = []
        stopped_count = 0
        for i, jid in enumerate(batch.job_ids):
            status = self._batch_manager._get_job_status(jid)
            if status is None:
                continue
            jobs.append(BatchJobRow(job_id=jid, index=i + 1, status=status))
            if status == JobStatus.STOPPED:
                stopped_count += 1

        return BatchSummaryViewModel(
            batch_id=batch_id,
            script_name=batch.script_name,
            total_jobs=len(batch.job_ids),
            aggregate_status=agg,
            jobs=tuple(jobs),
            stopped_count=stopped_count,
        )

    # ── 批量运行信号槽 ─────────────────────────────────────

    def _on_batch_created(self, batch_id: str) -> None:
        """BatchManager batch_created 信号处理：创建 BatchSummaryCard 并插入 UI。"""
        vm = self._build_batch_summary_view_model(batch_id)
        if vm is None:
            return

        card = BatchSummaryCard()
        card.update_view_model(vm)
        card.job_selected.connect(self._on_batch_job_selected)
        self._batch_cards[batch_id] = card
        # 插入到 stretch 之前
        self._batch_cards_layout.insertWidget(
            self._batch_cards_layout.count() - 1, card
        )
        self._batches_container.setVisible(True)

    def _on_batch_aggregate_changed(
        self, batch_id: str, _aggregate: object
    ) -> None:
        """BatchManager batch_aggregate_changed 信号处理：刷新卡片 view model。"""
        card = self._batch_cards.get(batch_id)
        if card is None:
            return
        vm = self._build_batch_summary_view_model(batch_id)
        if vm is not None:
            card.update_view_model(vm)

    def _on_batch_removed(self, batch_id: str) -> None:
        """BatchManager batch_removed 信号处理：移除卡片。"""
        card = self._batch_cards.pop(batch_id, None)
        if card is None:
            return
        self._batch_cards_layout.removeWidget(card)
        card.deleteLater()
        # 无剩余 batch 时隐藏整个区域
        if not self._batch_cards:
            self._batches_container.setVisible(False)

    def _on_batch_job_selected(self, job_id: str) -> None:
        """BatchSummaryCard job_selected 信号处理：切换到对应 output tab。"""
        self._on_job_card_clicked(job_id)

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

    def _on_job_finished(self, result: JobFinishResult) -> None:
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
            self._status_bar.showMessage(QCoreApplication.translate("JobPanelMixin", "任务 '{}' 已完成（退出码：0）").format(result.script_name), 5000)
        else:
            self._status_bar.showMessage(
                QCoreApplication.translate("JobPanelMixin", "任务 '{}' 失败（退出码：{}）").format(result.script_name, result.exit_code), 8000
            )

        # 在输出面板追加结束信息
        output = self._job_outputs.get(result.job_id)
        if output:
            banner = f"\n{'='*60}\n[{QCoreApplication.translate('JobPanelMixin', '进程结束')}] exit code: {result.exit_code}\n{'='*60}\n"
            output.append_output(banner, "stdout")
            output.set_finished()

        self._update_job_count()
        self._batch_manager.refresh()

    def _on_job_error(self, result: JobFinishResult) -> None:
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
        self._batch_manager.refresh()

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
                qt_format(QCoreApplication.translate("JobPanelMixin", "任务 '%1' 已运行 %2 秒。\n确定停止？"), job.script_entry.name, int(elapsed)),
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
                    qt_format(QCoreApplication.translate("JobPanelMixin", "任务 '%1' 正在运行。\n停止并关闭？"), job.script_entry.name),
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

    _RUN_STYLE_READY = RUN_BTN_STYLE_READY
    _RUN_STYLE_FULL = RUN_BTN_STYLE_FULL

    def _update_job_count(self) -> None:
        running = sum(1 for c in self._job_cards.values() if c.is_running)
        total = len(self._job_cards)
        if total == 0:
            self._job_count_label.setText(QCoreApplication.translate("JobPanelMixin", "任务"))
        else:
            self._job_count_label.setText(qt_format(QCoreApplication.translate("JobPanelMixin", "任务（%1 运行中，共 %2）"), running, total))

        self._status_bar.showMessage(
            qt_format(QCoreApplication.translate("JobPanelMixin", "%1 运行中，共 %2"), running, total)
            if running > 0
            else QCoreApplication.translate("JobPanelMixin", "就绪")
        )
