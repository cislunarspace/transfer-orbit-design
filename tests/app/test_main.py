"""Application entry point tests."""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest


def test_main_shows_window_maximized():
    """启动时主窗口应请求最大化，避免固定初始尺寸限制工作区。"""
    from src.app import main as app_main

    app = Mock()
    app.exec.return_value = 0
    window = Mock()
    project = Mock()
    project.artifacts = []

    with (
        patch("PyQt6.QtWidgets.QApplication", return_value=app),
        patch("src.commons.font_config.apply_cjk_font_fallback"),
        patch("src.commons.paths.detect_kernel_dir", return_value="/kernels"),
        patch("src.commons.kernels.kernel_dir_usable", return_value=True),
        patch.object(app_main, "_build_project_from_output", return_value=(project, 0.0)),
        patch("src.app.main_window.MainWindow", return_value=window),
        patch("sys.exit"),
    ):
        app_main.main()

    window.showMaximized.assert_called_once_with()
    window.show.assert_not_called()


@pytest.fixture()
def qapp():
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance()
    return app if app is not None else QApplication([])


def test_main_window_minimum_width_fits_960px_screen(qapp):
    """子组件的隐式最小宽度不得阻止窄屏最大化。"""
    from src.app.main_window import MainWindow

    with patch("src.app.main_window.discover_artifacts", return_value=[]):
        window = MainWindow()
    window.show()
    qapp.processEvents()

    assert window.minimumSizeHint().width() <= 960
    window.close()

