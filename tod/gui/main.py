"""GUI 入口 — python -m tod.gui.main

PyInstaller 打包后，exe 同时充当 Python 解释器运行子进程脚本。
"""

import os
import platform
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Qt 环境变量设置（在 frozen 模式检查之前，确保子进程也能获取）
# ---------------------------------------------------------------------------
# 屏蔽 Qt 字体后端的警告日志（Windows DirectWrite 兼容旧字体时的日志噪音）
os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.fonts=false;qt.text.font.db=false")

# Linux: 确保使用系统 GTK 主题以获得原生窗口装饰
# 仅在未设置时设置，允许用户覆盖
if platform.system() == "Linux":
    if "QT_QPA_PLATFORMTHEME" not in os.environ:
        os.environ["QT_QPA_PLATFORMTHEME"] = "gtk3"
    # Wayland + GNOME 默认使用 CSD (客户端装饰)，Qt 需要 X11 获得原生装饰
    if os.environ.get("XDG_SESSION_TYPE") == "wayland" and "QT_QPA_PLATFORM" not in os.environ:
        os.environ["QT_QPA_PLATFORM"] = "xcb"


# ---------------------------------------------------------------------------
# PyInstaller 子进程解释器模式
# ---------------------------------------------------------------------------
# GUI 的 JobManager 用 sys.executable 启动脚本；打包后 sys.executable
# 就是本 exe。检测到传入 .py 文件时，直接 exec 该脚本。
if getattr(sys, "frozen", False) and len(sys.argv) > 1:
    _maybe_script = sys.argv[1]
    if _maybe_script.endswith(".py") and Path(_maybe_script).is_file():
        _script_path = Path(_maybe_script).resolve()
        # 推导 repo_root：向上查找 pyproject.toml 所在目录
        _repo_root = _script_path.parent
        while _repo_root != _repo_root.parent:
            if (_repo_root / "pyproject.toml").exists():
                break
            _repo_root = _repo_root.parent
        # 安全白名单：仅允许执行项目 tod/ 目录下的脚本
        _tod_dir = (_repo_root / "tod").resolve()
        if not _script_path.is_relative_to(_tod_dir):
            print(f"[error] 拒绝执行非项目脚本: {_script_path}")
            sys.exit(1)
        # 让脚本看到正确的 sys.argv（去掉 exe 路径）
        sys.argv = sys.argv[1:]
        if str(_repo_root) not in sys.path:
            sys.path.insert(0, str(_repo_root))
        with open(_script_path, "r", encoding="utf-8") as _f:
            _code = compile(_f.read(), str(_script_path), "exec")
        exec(_code, {"__name__": "__main__", "__file__": str(_script_path)})
        sys.exit(0)

# 确保 repo root 在 sys.path 中
repo_root = Path(__file__).resolve().parent.parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from PyQt6 import QtWebEngineWidgets  # noqa: E402  # must import before QApplication
from PyQt6.QtGui import QIcon  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from tod.gui.main_window import MainWindow  # noqa: E402


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Transfer Orbit Design")
    window = MainWindow(repo_root=str(repo_root))

    # 设置窗口图标 (Linux: PNG → ICO 回退, macOS: ICNS → PNG 回退, Windows: ICO)
    icon = None
    if platform.system() == "Linux":
        icon_path = repo_root / "icon.png"
        if not icon_path.exists():
            icon_path = repo_root / "icon.ico"  # 回退到 ICO
        if icon_path.exists():
            icon = QIcon(str(icon_path))
    elif platform.system() == "Darwin":
        icon_path = repo_root / "icon.icns"
        if icon_path.exists():
            icon = QIcon(str(icon_path))
        else:
            # Fallback to PNG on macOS if ICNS not found
            icon_path = repo_root / "icon.png"
            if icon_path.exists():
                icon = QIcon(str(icon_path))
    else:
        icon_path = repo_root / "icon.ico"
        if icon_path.exists():
            icon = QIcon(str(icon_path))

    if icon and not icon.isNull():
        window.setWindowIcon(icon)

    window.show()
    app.aboutToQuit.connect(window._job_manager.stop_all)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
