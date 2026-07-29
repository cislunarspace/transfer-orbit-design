"""PyQt6 图形界面组件。

"""

import io
import multiprocessing
import multiprocessing.spawn
import os
import platform
import runpy
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
# PyInstaller frozen 模式初始化
# ---------------------------------------------------------------------------
if getattr(sys, "frozen", False):
    # multiprocessing spawn 的子进程会以 --multiprocessing-fork 参数重启本 exe，
    # freeze_support 负责接管 worker 引导，避免落入下方 GUI 分支重复弹窗
    multiprocessing.freeze_support()

    # windowed 子进程（multiprocessing spawn）没有控制台，sys.stdout/stderr 为 None，
    # 脚本 print 或引导代码写 traceback 时直接 AttributeError；重定向到 devnull 兜底。
    # GUI 经 QProcess 启动的脚本进程有管道，stdout/stderr 有效，不受影响。
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")

    # frozen 嵌入式解释器不响应 PYTHONUNBUFFERED / PYTHONIOENCODING，
    # sys.stdout/stderr 退化为系统代码页（中文 Windows=GBK）+ 块缓冲：
    # GUI 输出面板按 utf-8 解码得到乱码，长任务输出到进程退出才一次性冲刷。
    # 统一改为 utf-8 + 行缓冲，与 GUI 的解码约定一致、恢复流式输出。
    for _stream in (sys.stdout, sys.stderr):
        if isinstance(_stream, io.TextIOWrapper):
            _stream.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)

    # SPICE kernels 自动探测：exe 旁存在含 .bsp 的 kernels/ 目录时设为默认。
    # setdefault 保证用户显式设置优先；env 经 QProcessEnvironment 传给全部子进程
    _kernels_dir = Path(sys.executable).resolve().parent / "kernels"
    if _kernels_dir.is_dir() and any(_kernels_dir.glob("*.bsp")):
        os.environ.setdefault("SPICE_KERNEL_DIR", str(_kernels_dir))

# ---------------------------------------------------------------------------
# PyInstaller 子进程解释器模式
# ---------------------------------------------------------------------------
# GUI 的 JobManager 用 sys.executable 启动脚本；打包后 sys.executable
# 就是本 exe。检测到传入 .py 文件时，直接以 __main__ 身份运行该脚本。
# 必须用 runpy.run_path 而非裸 exec：后者不会替换 sys.modules["__main__"]，
# 脚本内 multiprocessing spawn 的 worker 反序列化函数时会找错模块。
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
        # multiprocessing spawn 支持：win32 下 CPython 把 frozen exe 视为 WINEXE
        # （spawn.py 中 WINEXE = getattr(sys, "frozen", False)），于是
        # get_preparation_data 不向子进程传 init_main_from_path，子进程的
        # __main__ 停留在 exe 入口 main.py，脚本内定义的 worker 函数反序列化失败。
        # 本分支里 exe 就是普通脚本解释器，__main__ 是被 runpy 执行的脚本，
        # 与非 frozen 行为一致，因此把 WINEXE 置回 False（它仅影响该分支判断）。
        multiprocessing.spawn.WINEXE = False
        runpy.run_path(str(_script_path), run_name="__main__")
        sys.exit(0)

# 确保 repo root 在 sys.path 中
repo_root = Path(__file__).resolve().parent.parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from PyQt6.QtCore import Qt  # noqa: E402
from PyQt6.QtGui import QIcon  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from tod.gui.main_window import MainWindow  # noqa: E402

def main() -> None:
    
    # QtWebEngine 需要共享 OpenGL 上下文；必须在 QApplication 实例化之前设置
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)

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
            # macOS 上若 ICNS 不存在则回退到 PNG
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
