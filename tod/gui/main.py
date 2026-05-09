"""GUI 入口 — python -m tod.gui.main

PyInstaller 打包后，exe 同时充当 Python 解释器运行子进程脚本。
"""

import os
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# PyInstaller 子进程解释器模式
# ---------------------------------------------------------------------------
# GUI 的 JobManager 用 sys.executable 启动脚本；打包后 sys.executable
# 就是本 exe。检测到传入 .py 文件时，直接 exec 该脚本。
if getattr(sys, "frozen", False) and len(sys.argv) > 1:
    _maybe_script = sys.argv[1]
    if _maybe_script.endswith(".py") and Path(_maybe_script).is_file():
        # 让脚本看到正确的 sys.argv（去掉 exe 路径）
        sys.argv = sys.argv[1:]
        # 推导 repo_root（脚本位于 tod/pipelines/.../xxx.py）
        _script_path = Path(_maybe_script).resolve()
        _repo_root = _script_path.parent
        while _repo_root.name != "tod" and _repo_root.parent != _repo_root:
            _repo_root = _repo_root.parent
        if _repo_root.name == "tod":
            _repo_root = _repo_root.parent
        if str(_repo_root) not in sys.path:
            sys.path.insert(0, str(_repo_root))
        # 运行脚本
        with open(_maybe_script, "r", encoding="utf-8") as _f:
            _code = compile(_f.read(), _maybe_script, "exec")
        exec(_code, {"__name__": "__main__", "__file__": str(_script_path)})
        sys.exit(0)

# 屏蔽 Qt 字体后端的警告日志（Windows DirectWrite 兼容旧字体时的日志噪音）
os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.fonts=false;qt.text.font.db=false")

# 确保 repo root 在 sys.path 中
repo_root = Path(__file__).resolve().parent.parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from PyQt6.QtWidgets import QApplication  # noqa: E402

from tod.gui.main_window import MainWindow  # noqa: E402


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Transfer Orbit Design")
    window = MainWindow(repo_root=str(repo_root))
    window.show()
    app.aboutToQuit.connect(window._job_manager.stop_all)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
