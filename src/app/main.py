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
    import sys

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
