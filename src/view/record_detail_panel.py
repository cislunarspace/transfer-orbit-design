"""记录详情面板 -- 选中产物的分类信息、谱系与教学标注（issue #375）。

展示 catalog 记录的多维分类（族 / 平动点 / Jacobi / 振幅 / 段存在性）、
谱系指针（上游被删时显示断链标记）与标注（tags/note）；标注经
``catalog_tag`` 落库，族成员可经 ``catalog_promote`` 提升为独立记录。
面板不直接调 catalog——所有动作以信号交给主窗口统一处理。
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from src.model.artifact import Artifact


class RecordDetailPanel(QWidget):
    """项目树下方的记录详情面板。

    Signals:
        tag_requested(str, list, str): 保存标注（record_id, tags, note）。
        promote_requested(str, int): 族成员提升（record_id, member_index）。
        control_requested(): 请求对当前记录执行轨道保持（主窗口弹对话框）。
    """

    tag_requested = pyqtSignal(str, list, str)
    promote_requested = pyqtSignal(str, int)
    control_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current_record_id: str | None = None
        self._current_member_count = 0

        self._info_label = QLabel("未选择记录")
        self._info_label.setWordWrap(True)
        self._info_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        # 教学标注：tags 逗号分隔，note 多行
        self._tags_edit = QLineEdit()
        self._tags_edit.setPlaceholderText("标签（逗号分隔）")
        self._note_edit = QPlainTextEdit()
        self._note_edit.setPlaceholderText("备注（教学注释）")
        self._note_edit.setMaximumHeight(72)
        save_btn = QPushButton("保存标注")
        save_btn.clicked.connect(self._on_save_clicked)

        # 族成员提升（仅族记录可见）
        self._member_row = QWidget()
        member_layout = QHBoxLayout(self._member_row)
        member_layout.setContentsMargins(0, 0, 0, 0)
        self._member_spin = QSpinBox()
        self._member_spin.setMinimum(0)
        promote_btn = QPushButton("提升成员为记录")
        promote_btn.clicked.connect(self._on_promote_clicked)
        member_layout.addWidget(QLabel("成员"))
        member_layout.addWidget(self._member_spin)
        member_layout.addWidget(promote_btn, 1)

        # 轨道保持入口：仅可作输入的产物（orbit/ephemeris 且有星历）可用
        self._control_btn = QPushButton("轨道保持…")
        self._control_btn.clicked.connect(lambda: self.control_requested.emit())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(QLabel("记录详情"))
        layout.addWidget(self._info_label)
        layout.addWidget(self._tags_edit)
        layout.addWidget(self._note_edit)
        layout.addWidget(save_btn)
        layout.addWidget(self._member_row)
        layout.addWidget(self._control_btn)

    # -- 公共 API -----------------------------------------------------------

    def show_record(
        self,
        artifact: Artifact,
        *,
        upstream_label: str | None = None,
        broken_lineage: bool = False,
    ) -> None:
        """展示一条记录的详情（谱系由调用方解析后传入）。"""
        self._current_record_id = artifact.record_id
        extra = artifact.extra
        self._current_member_count = int(extra.get("member_count") or 0)
        self._member_row.setVisible(artifact.artifact_type == "family")
        self._member_spin.setMaximum(max(self._current_member_count - 1, 0))

        # 轨道保持按钮：可用性判据与 ControlOrbitDialog 一致（单一来源），
        # 无星历输入（如提升的族成员只有 CR3BP 段）置灰并说明原因
        from src.view.control_orbit_dialog import can_control_artifact

        controllable = artifact.artifact_type in ("orbit", "ephemeris")
        self._control_btn.setVisible(controllable)
        has_input = can_control_artifact(artifact)
        self._control_btn.setEnabled(has_input)
        self._control_btn.setToolTip(
            "" if has_input else "该记录无星历段，无法轨道保持（可重新设计带星历的轨道）"
        )

        lines = [f"<b>{artifact.label}</b>"]
        family = extra.get("orbit_family") or ""
        if family:
            lines.append(f"族: {family}")
        if extra.get("libration_point"):
            lines.append(f"平动点: L{extra['libration_point']}")
        jacobi = extra.get("jacobi")
        if jacobi:
            lines.append(f"Jacobi: {jacobi[0]:.4f} – {jacobi[1]:.4f}")
        amplitude = extra.get("amplitude")
        if amplitude:
            lines.append(f"主振幅: {amplitude[0]:.0f} – {amplitude[1]:.0f} km")
        segments = []
        if extra.get("has_cr3bp"):
            segments.append("CR3BP")
        if extra.get("has_ephemeris"):
            segments.append("星历")
        if segments:
            lines.append(f"段: {' + '.join(segments)}")
        if artifact.artifact_type == "family":
            lines.append(f"成员数: {self._current_member_count}")
        lines.append(f"来源: {artifact.source_tool}")
        lines.append(f"创建: {artifact.created_at:%Y-%m-%d %H:%M}")
        source_id = extra.get("source_record_id")
        if source_id is None:
            pass  # 无谱系不显示
        elif broken_lineage:
            lines.append("谱系: ⚠ 上游记录已删除，本记录仍可使用")
        else:
            lines.append(f"谱系: ← {upstream_label or source_id}")
        self._info_label.setText("<br>".join(lines))

        self._tags_edit.setText(", ".join(extra.get("tags") or []))
        self._note_edit.setPlainText(extra.get("note") or "")

    def clear(self) -> None:
        """清空面板（未选中 / 非 catalog 产物）。"""
        self._current_record_id = None
        self._current_member_count = 0
        self._info_label.setText("未选择记录")
        self._tags_edit.clear()
        self._note_edit.clear()
        self._member_row.setVisible(False)
        self._control_btn.setVisible(False)

    # -- 内部 ---------------------------------------------------------------

    def _on_save_clicked(self) -> None:
        if self._current_record_id is None:
            return
        tags = [t.strip() for t in self._tags_edit.text().split(",") if t.strip()]
        self.tag_requested.emit(self._current_record_id, tags, self._note_edit.toPlainText())

    def _on_promote_clicked(self) -> None:
        if self._current_record_id is None:
            return
        self.promote_requested.emit(self._current_record_id, self._member_spin.value())
