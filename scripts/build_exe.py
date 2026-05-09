"""打包 GUI 为 Windows 可执行文件（PyInstaller）。

用法:
    python scripts/build_exe.py

输出:
    dist/TransferOrbitDesign/     -- onedir 模式，含 exe 及所有依赖
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    dist_dir = repo_root / "dist"
    build_dir = repo_root / "build"

    # 清理旧构建
    if build_dir.exists():
        shutil.rmtree(build_dir)
    if dist_dir.exists():
        shutil.rmtree(dist_dir)

    # 从 PyPI 安装 e2m2e，确保 PyInstaller 能发现它
    print("Installing e2m2e from PyPI...")
    r = subprocess.run(
        [sys.executable, "-m", "pip", "install", "e2m2e"],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        print("Failed to install e2m2e:")
        print(r.stderr)
        return 1
    print("e2m2e installed OK")

    # PyInstaller 参数
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--name", "TransferOrbitDesign",
        "--onedir",
        "--windowed",
        "--optimize", "2",
        # tod 包：需要 pipelines 脚本作为数据文件保留
        "--collect-all", "tod",
        # e2m2e 通过 import 链自动追踪
        "--collect-submodules", "e2m2e",
        # 科学计算库隐藏导入
        "--hidden-import", "numpy",
        "--hidden-import", "scipy",
        "--hidden-import", "matplotlib",
        "--hidden-import", "matplotlib.pyplot",
        "--hidden-import", "matplotlib.backends.backend_qtagg",
        "--hidden-import", "tqdm",
        # 排除不必要的大型模块以减小体积（标准库模块不排，避免间接依赖崩溃）
        "--exclude-module", "tkinter",
        "--exclude-module", "matplotlib.backends.backend_tkagg",
        "--exclude-module", "matplotlib.backends.backend_wx",
        "--exclude-module", "matplotlib.backends.backend_gtk",
        "--exclude-module", "matplotlib.backends.backend_cairo",
        "--exclude-module", "matplotlib.backends.backend_webagg",
        "--exclude-module", "IPython",
        "--exclude-module", "jupyter",
        "--exclude-module", "notebook",
        "--exclude-module", "pytest",
        "--exclude-module", "pydoc",
        "--exclude-module", "lib2to3",
        # 入口脚本
        str(repo_root / "tod" / "gui" / "main.py"),
    ]

    print("Running PyInstaller...")
    print(" ".join(cmd))
    result = subprocess.run(cmd, cwd=repo_root)

    if result.returncode != 0:
        print("PyInstaller failed!")
        return result.returncode

    exe_dir = dist_dir / "TransferOrbitDesign"
    exe_path = exe_dir / "TransferOrbitDesign.exe"

    if not exe_path.exists():
        print(f"ERROR: Expected exe not found at {exe_path}")
        return 1

    # 计算体积
    total_size = sum(f.stat().st_size for f in exe_dir.rglob("*") if f.is_file())
    print(f"\nBuild successful!")
    print(f"  Output: {exe_dir}")
    print(f"  Exe:    {exe_path}")
    print(f"  Size:   {total_size / 1024 / 1024:.1f} MB")

    return 0


if __name__ == "__main__":
    sys.exit(main())
