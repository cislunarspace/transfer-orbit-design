"""BatchSummaryCard — 批量运行摘要卡片（dumb view）。

展示一次批量运行的聚合状态与子任务列表：

- :class:`BatchJobRow` — 单行 job 不可变数据
- :class:`BatchSummaryViewModel` — 卡片完整渲染状态的不可变快照
- :class:`BatchSummaryCard(QWidget)` — dumb view，仅 ``update_view_model(vm)`` 渲染

设计约束：

- Card 不持有业务状态，不查询 BatchManager；所有推导（含"含 N 个已停止"副标题）
  发生在调用方，Card 只渲染 view model。
- 展开/折叠通过 ``setVisible`` 实现，无额外状态机。
- 颜色/文案集中引用 ``JOB_STATUS_DISPLAY`` / ``BATCH_AGGREGATE_DISPLAY``，
  不在 widget 内重新硬编码字符串。
"""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from tod.gui.batch import BATCH_AGGREGATE_DISPLAY, BatchAggregate
from tod.gui.jobs.job_status import JOB_STATUS_DISPLAY, JobStatus

# 聚合状态徽章颜色（集中维护，不在 widget 内硬编码）
# 与 output_panel._STATUS_COLORS 同一套双主题可读色板。
_AGGREGATE_BADGE_COLORS: dict[BatchAggregate, str] = {
    BatchAggregate.RUNNING: "#0078d4",
    BatchAggregate.SUCCESS: "#107c10",
    BatchAggregate.FAILURE: "#d13438",
    BatchAggregate.PARTIAL: "#ca5010",
    BatchAggregate.PARTIAL_WITH_STOPS: "#ca5010",
    BatchAggregate.STOPPED: "#ca5010",
}

@dataclass(frozen=True)
class BatchJobRow:
    """单行 job 的不可变数据。

    Attributes:
        job_id: 任务唯一标识（8 位 uuid 短 id）。
        index: 1-based 序号（用于展示 "#1", "#2" 等）。
        status: 当前 JobStatus。
    """

    job_id: str
    index: int
    status: JobStatus

@dataclass(frozen=True)
class BatchSummaryViewModel:
    """卡片完整渲染状态的不可变快照。

    Attributes:
        batch_id: 批量运行唯一标识。
        script_name: 工具显示名。
        total_jobs: 子任务总数。
        aggregate_status: 聚合状态枚举。
        jobs: 子任务行列表（按 dispatch 顺序）。
        stopped_count: 已停止任务数（用于 partial_with_stops 副标题）。
    """

    batch_id: str
    script_name: str
    total_jobs: int
    aggregate_status: BatchAggregate
    jobs: tuple[BatchJobRow, ...]
    stopped_count: int = 0

class BatchSummaryCard(QWidget):
    """批量运行摘要卡片，dumb view，仅 ``update_view_model(vm)`` 渲染。

    卡片结构：
    - 标题行：状态徽章 + 工具名 + 任务数 + 中文聚合状态
    - 副标题（partial_with_stops 时）：含 N 个已停止
    - 展开区：每个 job 的 "#index 状态中文 job_id 短码" 行

    单击标题行展开/折叠；单击任一行 emit ``job_selected(job_id)``。

    Signals:
        job_selected(job_id): 展开区某行被单击。
    """

    job_selected = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        # plain QWidget 默认不绘制样式表背景，开启后主题 QSS 的卡片外壳才生效
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self._current_vm: BatchSummaryViewModel | None = None

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 4, 8, 4)
        main_layout.setSpacing(0)

        # -- 标题行（单击展开/折叠） --
        self._header_widget = QWidget()
        self._header_widget.setCursor(Qt.CursorShape.PointingHandCursor)
        self._header_widget.mousePressEvent = self._toggle_details  # type: ignore[method-assign]  # pyright CI 报 QWidget 赋值不允许；运行时正确
        header_layout = QHBoxLayout(self._header_widget)
        header_layout.setContentsMargins(0, 4, 0, 4)
        header_layout.setSpacing(8)

        self._badge = QLabel()
        self._badge.setFixedWidth(14)
        header_layout.addWidget(self._badge)

        self._title_label = QLabel()
        self._title_label.setStyleSheet("font-weight: bold; font-size: 11px;")
        header_layout.addWidget(self._title_label)

        self._subtitle_label = QLabel()
        self._subtitle_label.setStyleSheet(
            "color: #ca5010; font-size: 10px;"
        )
        self._subtitle_label.setVisible(False)
        header_layout.addWidget(self._subtitle_label)

        header_layout.addStretch()

        main_layout.addWidget(self._header_widget)

        # -- 展开区（初始折叠） --
        self._details_widget = QWidget()
        details_layout = QVBoxLayout(self._details_widget)
        details_layout.setContentsMargins(16, 2, 0, 4)
        details_layout.setSpacing(2)
        self._details_layout = details_layout
        self._details_widget.setVisible(False)

        main_layout.addWidget(self._details_widget)

        # 外壳样式由主题 QSS 的 BatchSummaryCard 类选择器提供

    def update_view_model(self, vm: BatchSummaryViewModel) -> None:
        """根据 view model 更新卡片显示。"""
        self._current_vm = vm

        color = _AGGREGATE_BADGE_COLORS.get(vm.aggregate_status, "#808080")
        self._badge.setStyleSheet(f"color: {color}; font-size: 14px;")
        self._badge.setText("●")

        agg_display = BATCH_AGGREGATE_DISPLAY.get(
            vm.aggregate_status, str(vm.aggregate_status)
        )
        self._title_label.setText(
            f"{vm.script_name} ({vm.total_jobs}) — {agg_display}"
        )

        # partial_with_stops 副标题
        if (
            vm.aggregate_status == BatchAggregate.PARTIAL_WITH_STOPS
            and vm.stopped_count > 0
        ):
            self._subtitle_label.setText(
                f"含 {vm.stopped_count} 个已停止"
            )
            self._subtitle_label.setVisible(True)
        else:
            self._subtitle_label.setVisible(False)

        # 重建展开区行
        self._rebuild_rows(vm.jobs)

    def _rebuild_rows(self, jobs: tuple[BatchJobRow, ...]) -> None:
        """重建展开区 job 行（清空旧 widget 后创建新 widget）。"""
        # 移除旧行
        while self._details_layout.count():
            item = self._details_layout.takeAt(0)
            if item is None:
                continue
            w = item.widget()
            if w is not None:
                w.deleteLater()

        for row in jobs:
            status_display = JOB_STATUS_DISPLAY.get(row.status, str(row.status))
            short_id = row.job_id[:6]
            label = QLabel(f"#{row.index} {status_display} {short_id}")
            label.setStyleSheet("font-size: 10px;")
            label.setCursor(Qt.CursorShape.PointingHandCursor)
            label.mousePressEvent = lambda _e, jid=row.job_id: (  # type: ignore[method-assign]  # pyright CI 报 QLabel 赋值不允许；运行时正确
                self.job_selected.emit(jid)
            )
            self._details_layout.addWidget(label)

    def _toggle_details(self, _event) -> None:  # type: ignore[override]
        """单击标题行切换展开区可见性。"""
        visible = not self._details_widget.isVisible()
        self._details_widget.setVisible(visible)


