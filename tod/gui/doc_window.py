# pyright: reportArgumentType=false, reportOptionalMemberAccess=false, reportAttributeAccessIssue=false, reportGeneralTypeIssues=false, reportInvalidTypeForm=false, reportCallIssue=false, reportPrivateImportUsage=false
"""PyQt6 图形界面组件。

本模块为 Transfer Orbit Design 的脚本化工作流提供辅助类型、函数或入口。
"""


from __future__ import annotations

import html
import platform
from pathlib import Path

from PyQt6.QtCore import QUrl, Qt
from PyQt6.QtGui import QDesktopServices, QIcon
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QToolBar,
    QVBoxLayout,
    QWidget,
)


class DocWindow(QMainWindow):
    """Floating window for viewing documentation with navigation controls."""

    def __init__(self, repo_root: Path | str, parent=None):
        super().__init__(parent)
        self._repo_root = Path(repo_root)  # 确保是 Path 类型
        self._doc_root = self._repo_root / "docs" / "build" / "html"

        self.setWindowTitle("Documentation")
        self.resize(900, 700)

        # 设置窗口图标
        self._set_window_icon()

        self._setup_ui()

    def _set_window_icon(self) -> None:
        """Load and set the application window icon."""
        if platform.system() == "Linux":
            icon_path = self._repo_root / "icon.png"
            if not icon_path.exists():
                icon_path = self._repo_root / "icon.ico"  # 回退到 ICO
        elif platform.system() == "Darwin":
            icon_path = self._repo_root / "icon.icns"
            if not icon_path.exists():
                icon_path = self._repo_root / "icon.png"  # 回退到 PNG
        else:
            icon_path = self._repo_root / "icon.ico"

        if icon_path.exists():
            icon = QIcon(str(icon_path))
            if not icon.isNull():
                self.setWindowIcon(icon)

    def _setup_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Toolbar with navigation controls
        toolbar = QToolBar()
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        self._back_btn = QPushButton("◀")
        self._back_btn.setToolTip(self.tr("后退"))
        self._back_btn.setEnabled(False)
        toolbar.addWidget(self._back_btn)

        self._forward_btn = QPushButton("▶")
        self._forward_btn.setToolTip(self.tr("前进"))
        self._forward_btn.setEnabled(False)
        toolbar.addWidget(self._forward_btn)

        self._refresh_btn = QPushButton("⟳")
        self._refresh_btn.setToolTip(self.tr("刷新"))
        toolbar.addWidget(self._refresh_btn)

        toolbar.addSeparator()

        self._url_bar = QLineEdit()
        self._url_bar.setPlaceholderText(self.tr("文档 URL..."))
        self._url_bar.setReadOnly(True)
        self._url_bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        toolbar.addWidget(self._url_bar)

        self._open_ext_btn = QPushButton(self.tr("外部打开"))
        self._open_ext_btn.setToolTip(self.tr("在系统浏览器中打开"))
        toolbar.addWidget(self._open_ext_btn)

        # Web view
        self._web_view = QWebEngineView()
        layout.addWidget(self._web_view)

        # Connect signals
        self._back_btn.clicked.connect(self._web_view.back)
        self._forward_btn.clicked.connect(self._web_view.forward)
        self._refresh_btn.clicked.connect(self._web_view.reload)
        self._open_ext_btn.clicked.connect(self._open_in_external_browser)

        self._web_view.urlChanged.connect(self._on_url_changed)
        self._web_view.titleChanged.connect(self._on_title_changed)
        self._web_view.loadStarted.connect(self._on_load_started)
        self._web_view.loadFinished.connect(self._on_load_finished)

    def _update_nav_buttons(self) -> None:
        history = self._web_view.history()
        self._back_btn.setEnabled(history.canGoBack())
        self._forward_btn.setEnabled(history.canGoForward())

    def _on_url_changed(self, url: QUrl) -> None:
        self._url_bar.setText(url.toString())

    def _on_title_changed(self, title: str) -> None:
        if title and title != "Documentation":
            self.setWindowTitle(f"Documentation - {title}")

    def _on_load_started(self) -> None:
        self._update_nav_buttons()

    def _on_load_finished(self, success: bool) -> None:
        self._update_nav_buttons()
        if not success:
            self._show_error_page("Failed to load documentation page.")

    def _open_in_external_browser(self) -> None:
        url = self._web_view.url()
        if url.isValid():
            QDesktopServices.openUrl(url)

    def _get_doc_path(self, script_path: str) -> Path:
        """Convert script path to documentation path.

        Example: 'tod/generates/cr3bp/dro/generate_dro_family.py'
                 -> 'docs/build/html/tod/generates/cr3bp/dro/generate_dro_family.html'
        """
        # Remove .py extension and get relative path
        doc_rel = script_path
        if doc_rel.endswith(".py"):
            doc_rel = doc_rel[:-3]

        return self._doc_root / f"{doc_rel}.html"

    def load_script_doc(self, script_path: str) -> None:
        """Load documentation for a script.

        Args:
            script_path: The script path, e.g., 'tod/generates/cr3bp/dro/generate_dro_family.py'
        """
        doc_path = self._get_doc_path(script_path)

        if not doc_path.exists():
            self._show_error_page(f"Documentation not found for '{script_path}'")
            return

        url = QUrl.fromLocalFile(str(doc_path.absolute()))
        self._web_view.setUrl(url)
        self.setWindowTitle(f"Documentation - {Path(script_path).stem}")

    def _show_error_page(self, message: str) -> None:
        """Display an error page with the given message."""
        escaped_message = html.escape(message)
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                    background-color: #f5f5f5;
                }}
                .error-container {{
                    text-align: center;
                    padding: 40px;
                    background: white;
                    border-radius: 8px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }}
                h1 {{
                    color: #d32f2f;
                    margin-bottom: 16px;
                }}
                p {{
                    color: #666;
                    font-size: 16px;
                }}
            </style>
        </head>
        <body>
            <div class="error-container">
                <h1>⚠ Documentation Not Found</h1>
                <p>{escaped_message}</p>
                <p style="margin-top: 20px; font-size: 14px; color: #999;">
                    Build documentation with: sphinx-build -b html docs/source docs/build/html
                </p>
            </div>
        </body>
        </html>
        """
        self._web_view.setHtml(html_content)
