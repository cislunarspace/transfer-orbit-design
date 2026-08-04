"""原型入口 — 一键启动。

用法：
    uv run python -m tod.gui.prototype.run

原型标记：文件名含 run_prototype 以区别于正式入口。
"""

import os
import sys
from pathlib import Path

# 确保 repo root 在 sys.path 中
repo_root = Path(__file__).resolve().parent.parent.parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

# matplotlib 后端必须在任何 matplotlib 导入前设置
os.environ["MPLBACKEND"] = "Agg"


def main() -> None:
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QApplication

    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    app = QApplication(sys.argv)
    app.setApplicationName("e2m2e GUI Prototype")

    from tod.gui.prototype.prototype_window import PrototypeMainWindow

    window = PrototypeMainWindow(repo_root=str(repo_root))
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
