"""GUI 入口 — python scripts/gui/main.py"""

import sys
from pathlib import Path

# 确保 repo root 在 sys.path 中
repo_root = Path(__file__).resolve().parent.parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from PyQt6.QtWidgets import QApplication  # noqa: E402

from scripts.gui.main_window import MainWindow  # noqa: E402


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Transfer Orbit Design")
    window = MainWindow(repo_root=str(repo_root))
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
