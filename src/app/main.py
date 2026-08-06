"""Application entry point for transfer-orbit-design v2 GUI."""


def _build_project_from_output() -> tuple:
    """Scan the output/ directory and return (Project, scan_seconds).

    Returns a Project populated with any existing artifacts found under
    ``output/`` (relative to the repo root).  If the directory does not
    exist or contains no recognised JSON files the returned Project is
    simply empty.
    """
    import time
    from pathlib import Path

    from src.model import Project, discover_artifacts

    here = Path(__file__).resolve()
    repo_root = here.parent.parent.parent
    output_dir = repo_root / "output"

    t0 = time.perf_counter()
    artifacts = discover_artifacts(output_dir)
    elapsed = time.perf_counter() - t0

    project = Project(name="Transfer Orbit Design")
    for art in artifacts:
        project.add(art)

    return project, elapsed


def main() -> None:
    import os
    import sys

    from src.commons.paths import detect_kernel_dir

    # e2m2e pip 安装后闰秒内核自动搜索路径失效（见 detect_kernel_dir），
    # 必须在任何 import e2m2e 之前写入 SPICE_KERNEL_DIR，否则轨道设计报
    # SPICE(NOLEAPSECONDS)。
    kernel_dir = detect_kernel_dir()
    if kernel_dir:
        os.environ.setdefault("SPICE_KERNEL_DIR", kernel_dir)

    from PyQt6.QtWidgets import QApplication

    from src.commons.font_config import apply_cjk_font_fallback

    apply_cjk_font_fallback()

    app = QApplication(sys.argv)

    from src.app.main_window import MainWindow

    project, scan_seconds = _build_project_from_output()

    window = MainWindow(project=project)
    if scan_seconds > 0:
        window.show_scan_time(scan_seconds, len(project.artifacts))
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
