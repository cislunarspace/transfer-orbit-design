import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# 与 tod.gui.main 一致：在任何 QApplication 创建之前设 AA_ShareOpenGLContexts。
# 否则一旦 app 已存在，后续 import QtWebEngineWidgets 会报 ImportError（Qt 限制：
# QApplication 存在后不许 import WebEngine，除非设此 flag）。放在模块顶部确保
# 早于任何测试/fixture 创建 app。
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)

import pytest


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app
