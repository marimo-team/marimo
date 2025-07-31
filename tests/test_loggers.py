from __future__ import annotations

import logging
import os
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from unittest.mock import patch

import pytest

from marimo._loggers import (
    _LOG_LEVEL,
    _LOGGERS,
    get_log_directory,
    get_logger,
    make_log_directory,
    marimo_logger,
    set_level,
)


def test_set_level():
    original_level = _LOG_LEVEL

    # Test with integer levels
    set_level(logging.DEBUG)
    logger = get_logger("test1")
    assert logger.level == logging.DEBUG
    assert logger.handlers[0].level == logging.DEBUG

    set_level(logging.INFO)
    assert logger.level == logging.INFO
    assert logger.handlers[0].level == logging.INFO

    # Test with string levels
    for level in ["WARNING", "WARN", "DEBUG", "INFO", "ERROR", "CRITICAL"]:
        set_level(level)
        assert logger.level == min(logging._nameToLevel[level], logging.INFO)
        assert logger.handlers[0].level == logging._nameToLevel[level]

    # Test invalid levels
    with pytest.raises(ValueError):
        set_level("INVALID")

    with pytest.raises(ValueError):
        set_level(999)

    # Reset the log level
    set_level(original_level)


def test_get_logger():
    # Test basic logger creation
    logger1 = get_logger("test2")
    assert logger1.name == "test2"
    assert not logger1.propagate
    assert len(logger1.handlers) == 1

    # Test logger caching
    logger2 = get_logger("test2")
    assert logger1 is logger2  # Same logger instance

    # Test custom level
    logger3 = get_logger("test3", level=logging.DEBUG)
    assert logger3.level == logging.DEBUG

    # Test handlers
    handler = logger3.handlers[0]
    assert isinstance(handler, logging.StreamHandler)


def test_marimo_logger():
    logger = marimo_logger()
    assert logger.name == "marimo"
    first_handler = logger.handlers[0]
    assert isinstance(first_handler, logging.StreamHandler)
    second_handler = logger.handlers[1]
    assert isinstance(second_handler, logging.FileHandler)

    # Test file handler
    file_handler = next(
        h for h in logger.handlers if isinstance(h, logging.FileHandler)
    )
    assert isinstance(file_handler, TimedRotatingFileHandler)


def test_log_directory():
    # Test default directory
    default_dir = Path.home() / ".cache" / "marimo" / "logs"
    assert get_log_directory() == default_dir


def test_make_log_directory(tmp_path: Path):
    test_dir = tmp_path / "marimo_test_logs"

    with patch.dict(os.environ, {"XDG_CACHE_HOME": str(test_dir)}):
        make_log_directory()

    assert test_dir.exists()
    assert test_dir.is_dir()


def test_handler_levels():
    logger = marimo_logger()
    stream_handler = logger.handlers[0]
    file_handler = logger.handlers[1]
    assert isinstance(stream_handler, logging.StreamHandler)
    assert isinstance(file_handler, logging.FileHandler)

    # Test level changes affect stream handler but not file handler
    set_level(logging.WARNING)
    assert stream_handler.level == logging.WARNING
    assert file_handler.level == logging.INFO

    set_level(logging.DEBUG)
    assert stream_handler.level == logging.DEBUG
    assert file_handler.level == logging.DEBUG


@pytest.fixture(autouse=True)
def clear_loggers():
    # Clear the logger cache before each test
    _LOGGERS.clear()
    return
