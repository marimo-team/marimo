# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from marimo._utils.log_formatter import LogFormatter

# Global log level for loggers
_LOG_LEVEL = logging.WARNING

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
        logger.setLevel(_LOG_LEVEL)


def get_logger(name: str, level: Optional[int] = None) -> logging.Logger:
    if name in _LOGGERS:
        return _LOGGERS[name]

    logger = logging.getLogger(name)
    if level is None:
        logger.setLevel(_LOG_LEVEL)
    else:
        logger.setLevel(level)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(_LOG_FORMATTER)
    logger.addHandler(stream_handler)
    _LOGGERS[name] = logger
    logger.propagate = False
    return logger


def marimo_logger() -> logging.Logger:
    return get_logger("marimo")


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
