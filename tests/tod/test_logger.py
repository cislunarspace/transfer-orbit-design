"""Tests for tod.commons.logger — shared logging configuration."""

import logging

from tod.commons.logger import configure_logging, get_logger


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
