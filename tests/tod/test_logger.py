"""Tests for tod.commons.logger — shared logging configuration."""

import logging
import re
from pathlib import Path

from tod.commons.logger import configure_logging, get_logger

_REPO_ROOT = Path(__file__).resolve().parents[2]

# Directories that must be free of bare print() calls per issue #44.
_NO_PRINT_DIRS = [
    "tod/generates",
    "tod/transfers",
    "tod/plot",
    "tod/commons",
]


class TestGetLogger:
    def test_returns_logger_with_module_name(self):
        logger = get_logger("tod.generates.dro")
        assert logger.name == "tod.generates.dro"

    def test_returns_logging_logger_instance(self):
        logger = get_logger("test.module")
        assert isinstance(logger, logging.Logger)


class TestConfigureLogging:
    def test_default_level_is_info(self):
        configure_logging()
        root = logging.getLogger("tod")
        assert root.level == logging.INFO

    def test_custom_level_debug(self):
        configure_logging(level=logging.DEBUG)
        root = logging.getLogger("tod")
        assert root.level == logging.DEBUG

    def test_custom_level_warning(self):
        configure_logging(level=logging.WARNING)
        root = logging.getLogger("tod")
        assert root.level == logging.WARNING

    def test_has_stream_handler(self):
        configure_logging()
        root = logging.getLogger("tod")
        handlers = [h for h in root.handlers if isinstance(h, logging.StreamHandler)]
        assert len(handlers) >= 1

    def test_reconfigure_updates_level(self):
        configure_logging(level=logging.DEBUG)
        configure_logging(level=logging.WARNING)
        root = logging.getLogger("tod")
        assert root.level == logging.WARNING

    def test_child_logger_inherits_level(self):
        configure_logging(level=logging.WARNING)
        child = logging.getLogger("tod.generates.dro")
        assert child.getEffectiveLevel() == logging.WARNING


class TestNoBarePrint:
    """Issue #44: target directories must not contain bare print() calls."""

    def test_no_print_in_target_directories(self):
        failures: list[str] = []
        for rel_dir in _NO_PRINT_DIRS:
            target = _REPO_ROOT / rel_dir
            if not target.is_dir():
                continue
            for py_file in target.rglob("*.py"):
                text = py_file.read_text(encoding="utf-8")
                for lineno, line in enumerate(text.splitlines(), start=1):
                    stripped = line.lstrip()
                    if stripped.startswith("#"):
                        continue
                    if re.search(r"\bprint\s*\(", stripped):
                        rel = py_file.relative_to(_REPO_ROOT)
                        failures.append(f"{rel}:{lineno}: {line.strip()}")
        assert not failures, (
            f"Found {len(failures)} print() calls in target directories:\n"
            + "\n".join(failures)
        )
