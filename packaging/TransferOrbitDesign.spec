# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Transfer Orbit Design GUI.

扁平便携布局（contents_directory="."）：sys._MEIPASS == exe 所在目录，
src/ 源码、pyproject.toml、data/ 种子数据与 exe 平级，与开发仓库布局一致。
新 GUI 是进程内 QThread 直接调用 e2m2e 算法层，不依赖磁盘 .py 扫描；
收集 src/ 只为在 frozen 下保持 src.app.main 的相对导入深度
（main.py 里 repo_root = here.parent.parent.parent，需 src/ 完整平铺）。

onedir 是硬需求：exe 与 kernels/、output/ 等运行时目录共存于同一文件夹。

EXE 使用 exclude_binaries=True，二进制与数据只经 COLLECT 收集一次，
避免同时产出 onefile 与 onedir 两份冗余产物。
"""

from pathlib import Path

# SPECPATH 是 spec 所在目录（packaging/），其 parent 才是项目根
repo_root = Path(SPECPATH).resolve().parent

# Collect data files
datas = [
    # src/ 全部源码：新 GUI 在进程内 QThread 直接调 e2m2e 算法层，
    # 收集源码以保持 frozen 下 src/app/main.py 的相对导入深度
    (str(repo_root / "src"), "src"),
    # find_project_root 的项目根标记（frozen 包内没有 .git）
    (str(repo_root / "pyproject.toml"), "."),
    # CR3BP 种子数据（轨道族生成的参考初值，旧 CLI 脚本仍被 e2m2e 使用）
    (str(repo_root / "data" / "cr3bp_data" / "raw"), "data/cr3bp_data/raw"),
]

# Include icon if present
icon_path = repo_root / "icon.ico"
if icon_path.exists():
    # GUI 运行时从 repo_root/icon.ico 读取窗口图标（区别于 EXE 内嵌图标资源）
    datas.append((str(icon_path), "."))

a = Analysis(
    [str(repo_root / "src" / "app" / "main.py")],
    pathex=[str(repo_root)],
    binaries=[],
    datas=datas,
    hiddenimports=[
        # PyQt6 submodules used by the application
        "PyQt6.QtWebEngineWidgets",
        "PyQt6.QtWebEngineCore",
        "PyQt6.sip",
        # e2m2e submodules referenced across the codebase（新路径）
        # 新 GUI（src/engine/facade_bridge.py）直接 import e2m2e 算法层新路径模块，
        # 显式列出以兜底 PyInstaller 静态分析漏收。
        "e2m2e.algorithm.dynamics",
        "e2m2e.algorithm.station_keeping",
        "e2m2e.data.types.orbit",
        "e2m2e.data.kernels.manager",
        "e2m2e.data.templates.enums",
        "e2m2e.algorithm.solver",
        "e2m2e.algorithm.stability",
        "e2m2e.algorithm.family",
        "e2m2e.algorithm.ephemeris_correction",
        "e2m2e.algorithm.transfer.transfer_search",
        "e2m2e.algorithm.coordinate.synodic_j2000",
        # Matplotlib backends commonly needed
        "matplotlib.backends.backend_qtagg",
        # plot_interactive_orbit_inspector 使用，frozen 下需能加载
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