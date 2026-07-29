# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Transfer Orbit Design GUI.

扁平便携布局（contents_directory="."）：sys._MEIPASS == exe 所在目录，
tod/ 源码、pyproject.toml、data/ 种子数据与 exe 平级，与开发仓库布局一致。
这样 frozen 模式下扫描器（rglob *.py）、子进程解释器（runpy 执行 .py）、
find_project_root 的 pyproject.toml 标记查找都无需额外适配即可工作。

onedir 是硬需求：GUI 的 JobManager 以子进程方式执行 tod/ 下的 .py 脚本
（sys.executable + script_path），要求脚本源码真实存在于磁盘上。

EXE 使用 exclude_binaries=True，二进制与数据只经 COLLECT 收集一次，
避免同时产出 onefile 与 onedir 两份冗余产物。
"""

from pathlib import Path

# SPECPATH 是 spec 所在目录（packaging/），其 parent 才是项目根
repo_root = Path(SPECPATH).resolve().parent

# Collect data files
datas = [
    # tod/ 全部源码：扫描器与子进程 runpy 都依赖磁盘上的 .py 文件（含 i18n 资源）
    (str(repo_root / "tod"), "tod"),
    # find_project_root 的项目根标记（frozen 包内没有 .git）
    (str(repo_root / "pyproject.toml"), "."),
    # CR3BP 种子数据（轨道族生成的参考初值）
    (str(repo_root / "data" / "cr3bp_data" / "raw"), "data/cr3bp_data/raw"),
]

# Include icon if present
icon_path = repo_root / "icon.ico"
if icon_path.exists():
    # GUI 运行时从 repo_root/icon.ico 读取窗口图标（区别于 EXE 内嵌图标资源）
    datas.append((str(icon_path), "."))

a = Analysis(
    [str(repo_root / "tod" / "gui" / "main.py")],
    pathex=[str(repo_root)],
    binaries=[],
    datas=datas,
    hiddenimports=[
        # PyQt6 submodules used by the application
        "PyQt6.QtWebEngineWidgets",
        "PyQt6.QtWebEngineCore",
        "PyQt6.sip",
        # e2m2e submodules referenced across the codebase
        "e2m2e.core",
        "e2m2e.core.orbit",
        "e2m2e.algorithms",
        "e2m2e.algorithms.ephemeris_correction",
        "e2m2e.algorithms.stability",
        "e2m2e.orbits.geo",
        "e2m2e.orbits.leo",
        "e2m2e.propagator",
        "e2m2e.transfer",
        "e2m2e.utils",
        "e2m2e.visualization",
        "e2m2e.visualization.base",
        # Matplotlib backends commonly needed
        "matplotlib.backends.backend_qtagg",
        # plot_interactive_orbit_inspector 使用，frozen 下扫描器需能加载
        "mpl_toolkits.axes_grid1",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="TransferOrbitDesign",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(icon_path) if icon_path.exists() else None,
    # 扁平布局：禁用 _internal 子目录，全部内容与 exe 平级（COLLECT 会继承此设置），
    # 使 sys._MEIPASS == exe 所在目录，包布局与开发仓库一致
    contents_directory=".",
)

# COLLECT is required for onedir mode to gather all outputs into dist/
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="TransferOrbitDesign",
)
