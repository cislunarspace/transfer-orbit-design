# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for tod sidecar（e2m2e serve-stdio，ADR 0035）。

onefile + windowed：单文件便于 tauri resources（binaries/* 通配）随安装器
分发；windowed 避免 Windows 上被 GUI 拉起时闪控制台窗口，协议走
stdin/stdout 管道不受影响。

与退役的旧 GUI spec（TransferOrbitDesign.spec，PyQt 时代）不同：sidecar
自带全部 e2m2e 依赖；SPICE 内核不打包，安装目录 resources 自带 kernels/
小内核，cwd 由 Tauri 壳指向 resource 根（e2m2e Config 按 cwd 相对解析），
.bsp 星历内核沿用 scripts/download_kernels.py 按需获取。

构建：uv run pyinstaller packaging/tod_sidecar.spec --noconfirm
产物：dist/tod-sidecar(.exe)，随后复制到 src-tauri/binaries/ 供 tauri 打包。
"""

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# SPECPATH 是 spec 所在目录（packaging/）
spec_dir = Path(SPECPATH).resolve()

datas = collect_data_files("e2m2e")
binaries = []
hiddenimports = [
    # calcephpy（e2m2e→r2s2 传递依赖）为 C 扩展包，可能经懒加载躲过静态分析
    "calcephpy",
    # e2m2e CLI 与协议层入口（serve-stdio 路径）
    "e2m2e.api.cli.main",
    "e2m2e.api.sidecar",
    "e2m2e.api.facade",
    "e2m2e.api.config",
]
hiddenimports += collect_submodules("e2m2e") + collect_submodules("r2s2")

a = Analysis(
    [str(spec_dir / "sidecar_main.py")],
    pathex=[str(spec_dir.parent)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="tod-sidecar",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)