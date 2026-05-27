"""PyQt6 图形界面组件。

本模块为 Transfer Orbit Design 的脚本化工作流提供辅助类型、函数或入口。
"""


from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import QLabel


class ClickableLabel(QLabel):
    """一个在鼠标按下时发出 clicked 信号的 QLabel。"""

    clicked = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, ev: QMouseEvent | None) -> None:
        """执行 mousePressEvent 对应的处理逻辑。

        Args:
            ev: 调用方传入的参数值。

        Returns:
            None。
        """
        if ev and ev.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(ev)


class DocLinkMixin:
    """用于处理可点击文档链接的 Mixin。

    提供：
    - 文档链接点击信号
    - 将脚本路径解析为文档 URL 的辅助方法
    """

    doc_link_clicked = pyqtSignal(str)  # 文档链接被点击时发出 script_path
    _repo_root: Path

    def _get_doc_url(self, script_path: str) -> str | None:
        """将脚本路径转换为文档的 file:// URL。

        Args:
            script_path: 脚本路径，例如 'tod/generates/cr3bp/dro/generate_dro_family.py'

        Returns:
            文档的 file:// URL，若文档不存在则返回 None。
        """
        doc_rel = script_path
        if doc_rel.endswith(".py"):
            doc_rel = doc_rel[:-3]

        doc_path = self._repo_root / "docs" / "build" / "html" / f"{doc_rel}.html"

        if doc_path.exists():
            return doc_path.absolute().as_uri()

        return None


def make_doc_link_label(title: str, url: str | None, parent=None) -> ClickableLabel:
    """创建一个样式化为超链接的可点击标签。

    Args:
        title: 标签文本
        url: 点击时要打开的 URL（None 表示禁用链接）
        parent: 父级控件

    Returns:
        配置为可点击链接的 ClickableLabel。
    """
    if url:
        style = """
           QLabel {
                color: #0066cc;
                text-decoration: underline;
                font-size: 15px;
                font-weight: bold;
                padding: 4px 0;
            }
            ClickableLabel:hover {
                color: #004499;
            }
        """
    else:
        style = """
            QLabel {
                color: #999999;
                font-size: 15px;
                font-weight: bold;
                padding: 4px 0;
            }
        """

    label = ClickableLabel(title, parent)
    label.setStyleSheet(style)
    label.setTextInteractionFlags(label.textInteractionFlags() | label.textInteractionFlags().TextSelectableByMouse)

    if url:
        label.setProperty("doc_url", url)

    return label
