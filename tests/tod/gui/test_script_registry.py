"""Tests for tod.gui.script_registry."""

from pathlib import Path

import tod
from tod.gui.script_registry import SCRIPTS

# Project root: parent of the `tod/` package directory.
PROJECT_ROOT = Path(tod.__file__).resolve().parent.parent


def test_all_registered_script_paths_exist() -> None:
    """Every script_path registered in SCRIPTS must point to a real file."""
    missing: list[str] = []
    for category, entries in SCRIPTS.items():
        for entry in entries:
            full_path = PROJECT_ROOT / entry.script_path
            if not full_path.is_file():
                missing.append(f"[{category}] {entry.name}: {entry.script_path}")

    assert not missing, (
        f"The following registered script paths do not exist on disk:\n"
        + "\n".join(missing)
    )
