"""Mixin for handling documentation links in the GUI."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import QLabel


class ClickableLabel(QLabel):
    """A QLabel that emits a clicked signal when mouse is pressed."""

    clicked = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class DocLinkMixin:
    """Mixin for handling clickable documentation links.

    Provides:
    - Signal for doc link clicks
    - Helper to resolve script paths to doc URLs
    """

    doc_link_clicked = pyqtSignal(str)  # Emits script_path when doc link is clicked

    def _get_doc_url(self, script_path: str) -> str | None:
        """Convert script path to file:// URL for documentation.

        Args:
            script_path: The script path, e.g., 'tod/generates/cr3bp/dro/generate_dro_family.py'

        Returns:
            file:// URL to the documentation, or None if doc doesn't exist.
        """
        doc_rel = script_path
        if doc_rel.endswith(".py"):
            doc_rel = doc_rel[:-3]

        doc_path = self._repo_root / "docs" / "build" / "html" / f"{doc_rel}.html"

        if doc_path.exists():
            return f"file://{doc_path.absolute()}"

        return None


def make_doc_link_label(title: str, url: str | None, parent=None) -> ClickableLabel:
    """Create a clickable label styled as a hyperlink.

    Args:
        title: The label text
        url: The URL to open when clicked (None to disable link)
        parent: Parent widget

    Returns:
        ClickableLabel configured as a clickable link.
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
