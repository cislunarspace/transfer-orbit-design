# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Transfer Orbit Design GUI.

Builds an onedir bundle because the frozen-mode subprocess execution in
main.py needs access to the .py script files in the tod/ package.
"""

from pathlib import Path

# SPECPATH is the directory containing this .spec file (now packaging/),
# so its parent is the actual project root.
repo_root = Path(SPECPATH).resolve().parent

# Collect data files
datas = [
    (str(repo_root / "tod" / "gui" / "i18n" / "*.qm"), "tod/gui/i18n"),
    (str(repo_root / "tod" / "gui" / "i18n" / "*.json"), "tod/gui/i18n"),
]

# Include icon if present
icon_path = repo_root / "icon.ico"

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
    a.binaries,
    a.datas,
    [],
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
