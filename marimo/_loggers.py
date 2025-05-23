# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Optional

from marimo._utils.log_formatter import LogFormatter

# This file manages and creates loggers used throughout marimo.
#
# It contains a global log level, which can be updated and all handlers
# will be updated to use the new level.
#
# Our loggers contain two handlers:
# - A StreamHandler to stdout
# - A FileHandler to a rotating log file
#
# The stream handler is set to the global log level, but the file handler
# is set to either INFO or DEBUG, depending on the global log level.
#
# NB: As is best practice for Python libraries, we do not configure the
# root logger, and in particular we don't call basicConfig() (which would
# preclude client of our library from configuring the root logger to their
# own end).
# See https://docs.python.org/3/howto/logging.html#configuring-logging-for-a-library

# Global log level for loggers
_LOG_LEVEL: int = logging.WARNING

# Custom log formatter
_LOG_FORMATTER = LogFormatter()

# Cache of initialized loggers
_LOGGERS: dict[str, logging.Logger] = {}


def log_level_string_to_int(level: str) -> int:
    level = level.upper()
    if level == "DEBUG":
        return logging.DEBUG
    elif level == "INFO":
        return logging.INFO
    elif level == "WARN":
        return logging.WARNING
    elif level == "WARNING":
        return logging.WARNING
    elif level == "ERROR":
        return logging.ERROR
    elif level == "CRITICAL":
        return logging.CRITICAL
    else:
        raise ValueError(f"Unrecognized log level {level}")


def set_level(level: str | int = logging.WARNING) -> None:
    """Globally set the log level for all loggers."""

    global _LOG_LEVEL
    if isinstance(level, str):
        _LOG_LEVEL = log_level_string_to_int(level)
    elif level not in [
        logging.DEBUG,
        logging.INFO,
        logging.WARNING,
        logging.ERROR,
        logging.CRITICAL,
    ]:
        raise ValueError(f"Unrecognized log level {level}")
    else:
        _LOG_LEVEL = level

    for logger in _LOGGERS.values():
        # We have to set update the logger's level in order
        # for its handlers level's to be respected.
        # but it needs to be set to the minimum LOG_LEVEL and INFO
        # so the file handler can still pick it up
        logger.setLevel(min(_LOG_LEVEL, logging.INFO))
        for handler in logger.handlers:
            if isinstance(handler, logging.FileHandler):
                # Don't increase the log level of a file handler
                handler.setLevel(min(_LOG_LEVEL, handler.level))
            elif isinstance(handler, logging.StreamHandler):
                handler.setLevel(_LOG_LEVEL)


def get_logger(name: str, level: Optional[int] = None) -> logging.Logger:
    """
    Get a logger with a given name and level.
    If the logger is already created, we return the cached logger.
    Otherwise, we create a new logger and cache it.
    """

    # Cache loggers
    if name in _LOGGERS:
        return _LOGGERS[name]

    # Create logger
    logger = logging.getLogger(name)

    # Stream to stdout
    # We set the level on the StreamHandler, instead of the Logger,
    # because the FileHandler may have a different level
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(_LOG_FORMATTER)
    if level is None:
        stream_handler.setLevel(_LOG_LEVEL)
        logger.setLevel(_LOG_LEVEL)
    else:
        stream_handler.setLevel(level)
        logger.setLevel(level)

    logger.addHandler(stream_handler)

    # Cache logger
    _LOGGERS[name] = logger

    # Don't propagate to parent loggers
    logger.propagate = False
    return logger


has_added_handler = False


def marimo_logger() -> logging.Logger:
    """Get a logger for marimo."""
    logger = get_logger("marimo")

    # Add file handler to log to file
    global has_added_handler
    if not has_added_handler:
        has_added_handler = True
        logger.addHandler(_file_handler())

    return logger


def get_log_directory() -> Path:
    import os

    xdg_cache_home = os.getenv("XDG_CACHE_HOME", None)
    if xdg_cache_home is None:
        return Path.home() / ".cache" / "marimo" / "logs"
    return Path(xdg_cache_home) / "marimo" / "logs"


def make_log_directory() -> None:
    try:
        log_dir = get_log_directory()
        log_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        marimo_logger().debug(f"Failed to create log directory: {e}")


def _file_handler() -> logging.FileHandler:
    make_log_directory()

    # We log to the same file daily, and keep the last 7 days of logs
    file_handler = TimedRotatingFileHandler(
        get_log_directory() / "marimo.log",
        when="D",
        interval=1,
        backupCount=7,
        encoding="utf-8",
    )
    file_log_formatter = LogFormatter(
        fmt="[%(asctime)s] %(levelname)-8s %(name)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        color=False,
    )
    file_handler.setFormatter(file_log_formatter)

    # We set this to either INFO or DEBUG, depending on the global log level
    file_handler.setLevel(min(_LOG_LEVEL, logging.INFO))

    return file_handler
