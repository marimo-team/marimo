from __future__ import annotations

import logging

import pytest

from marimo._loggers import (
    _LOGGERS,
    get_logger,
    set_level,
)


def test_set_level():
    # Test with integer levels
    set_level(logging.DEBUG)
    logger = get_logger("test1")
    assert logger.level == logging.DEBUG

    set_level(logging.INFO)
    assert logger.level == logging.INFO

    # Test with string levels
    for level in ["WARNING", "WARN", "DEBUG", "INFO", "ERROR", "CRITICAL"]:
        set_level(level)
        assert logger.level == logging._nameToLevel[level]

    # Test invalid levels
    with pytest.raises(ValueError):
        set_level("INVALID")

    with pytest.raises(ValueError):
        set_level(999)


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


@pytest.fixture(autouse=True)
def clear_loggers():
    # Clear the logger cache before each test
    _LOGGERS.clear()
    return
