"""运行前确认对话框。

封装「运行前确认」领域概念：用户点击"运行"后、Job 创建前，向用户展示工具名、
当前选择文件、任务计划（按 chip 分组）、输出文件影响（覆盖目标），等待用户
显式确认；取消时 0 个 Job 创建（参见 issue #181 + ADR 0003）。

设计要点：
- **数据 / 视图分离**：dialog 接收 :class:`RunPlan`，不依赖 ScriptTabWidget 或 MainWindow。
- **静态入口** ``show_and_confirm``：测试和 MainWindow 都通过此入口调用。
- **i18n 集中**：所有用户可见文本在 ``__init__`` 缓存为 ``self.tr()``，便于翻译回退。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from tod.gui.run_orchestrator import OverwriteTarget, RunPlan


class RunConfirmationDialog(QDialog):
    """展示 RunPlan 并等待用户确认的对话框。

    静态方法 :meth:`show_and_confirm` 是推荐入口；测试可直接调用。
    """

    def __init__(self, plan: "RunPlan", parent: QWidget | None = None):
        super().__init__(parent)
        self._plan = plan
        # 缓存所有用户可见文本
        self._text_input_label = self.tr("当前选择文件")
        self._text_input_none = self.tr("（无）")
        self._text_task_section = self.tr("任务计划")
        self._text_single_task = self.tr("将运行 1 个任务")
        self._text_batch_tasks = self.tr("将批量运行 {n} 个任务")
        self._text_output_section = self.tr("输出文件影响")
        self._text_no_output_file = self.tr("（工具未指定输出文件参数）")
        self._text_overwrite_label = self.tr("覆盖文件")
        self._text_overwrite_shared = self.tr("（{n} 个任务共享此文件）")
        self._text_shared_suffix = self.tr("（{n} 个任务）")
        self._text_confirm_button = self.tr("确认运行")
        self._text_cancel_button = self.tr("取消")
        self._text_window_title = self.tr("{name} — 运行前确认")

        self.setWindowTitle(self._text_window_title.format(name=plan.entry.name))
        self.setModal(True)
        self.setMinimumWidth(480)

        layout = QVBoxLayout(self)

        # 当前选择文件
        if plan.file_input is not None:
            input_text = f"{self._text_input_label}：{plan.file_input}"
        else:
            input_text = f"{self._text_input_label}：{self._text_input_none}"
        layout.addWidget(QLabel(input_text))

        # 任务计划
        layout.addWidget(QLabel(self._text_task_section))
        if plan.total_tasks == 1:
            layout.addWidget(QLabel(self._text_single_task))
        else:
            layout.addWidget(
                QLabel(
                    self._text_batch_tasks.format(n=plan.total_tasks)
                )
            )
            list_widget = QListWidget()
            for group in plan.chip_groups:
                item = QListWidgetItem(f"[{group.group_value}] — {len(group.specs)} 个任务")
                list_widget.addItem(item)
            layout.addWidget(list_widget)

        # 输出文件影响
        layout.addWidget(QLabel(self._text_output_section))
        if plan.overwrites:
            list_widget = QListWidget()
            for target in plan.overwrites:
                if target.shared_count > 1:
                    text = f"{self._text_overwrite_label}：{target.path} {self._text_shared_suffix.format(n=target.shared_count)}"
                else:
                    text = f"{self._text_overwrite_label}：{target.path}"
                list_widget.addItem(QListWidgetItem(text))
            layout.addWidget(list_widget)
        elif plan.has_output_file_param:
            layout.addWidget(QLabel(self._text_no_output_file))
        # else: 既无 --output-file 参数，也无覆盖目标 — 跳过该节

        # 确认 / 取消
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        ok_btn = button_box.button(QDialogButtonBox.StandardButton.Ok)
        if ok_btn is not None:
            ok_btn.setText(self._text_confirm_button)
        cancel_btn = button_box.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel_btn is not None:
            cancel_btn.setText(self._text_cancel_button)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    @staticmethod
    def show_and_confirm(plan: "RunPlan", parent: QWidget | None = None) -> bool:
        """弹出对话框并返回用户是否确认。"""
        dialog = RunConfirmationDialog(plan, parent)
        return dialog.exec() == QDialog.DialogCode.Accepted
