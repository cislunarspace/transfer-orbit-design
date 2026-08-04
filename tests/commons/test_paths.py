"""tests for src.commons.paths"""

from pathlib import Path

from src.commons.paths import OUTPUT_DIR


class TestOutputDir:
    def test_points_to_repo_root_output(self):
        assert OUTPUT_DIR.name == "output"
        # OUTPUT_DIR should be the repo root's output/, anchored to paths.py location
        assert OUTPUT_DIR.parent == Path(__file__).resolve().parent.parent.parent

    def test_is_absolute(self):
        assert OUTPUT_DIR.is_absolute()
