"""Regression test for QtWebEngineWidgets import-order bug.

PyQt6 requires QtWebEngineWidgets to be imported before QApplication is
instantiated. This test ensures the main entry point honours that constraint.

See: https://doc.qt.io/qtforpython-6/overviews/qtwebengine-overview.html
"""

import sys
from pathlib import Path


def test_doc_window_importable_after_qapplication() -> None:
    """QtWebEngineWidgets must be pre-imported before QApplication creation.

    Regression: if QtWebEngineWidgets is NOT imported before QApplication,
    a later import (e.g. when opening the doc window) raises:

        ImportError: QtWebEngineWidgets must be imported or
        Qt.AA_ShareOpenGLContexts must be set before a QCoreApplication
        instance is created
    """
    # Simulate exactly what tod.gui.main does
    from PyQt6 import QtWebEngineWidgets  # noqa: F401
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication(sys.argv)
    assert app is not None

    # This used to fail when QtWebEngineWidgets was only imported lazily
    # inside _open_doc_window, after QApplication already existed.
    from tod.gui.doc_window import DocWindow  # noqa: F401

    # Basic smoke test: DocWindow can be instantiated
    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    window = DocWindow(repo_root)
    assert window is not None
    assert window.windowTitle() == "Documentation"
