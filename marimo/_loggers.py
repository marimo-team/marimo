# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import logging
from typing import Optional

from marimo._utils.log_formatter import LogFormatter

# Global log level for loggers
_LOG_LEVEL = logging.WARNING

# Custom log formatter
_LOG_FORMATTER = LogFormatter()

# Cache of initialized loggers
_LOGGERS: dict[str, logging.Logger] = {}


def set_level(level: str | int = logging.WARNING) -> None:
    global _LOG_LEVEL
    if isinstance(level, str):
        level = level.upper()
        if level == "DEBUG":
            _LOG_LEVEL = logging.DEBUG
        elif level == "INFO":
            _LOG_LEVEL = logging.INFO
        elif level == "WARN":
            _LOG_LEVEL = logging.WARNING
        elif level == "ERROR":
            _LOG_LEVEL = logging.ERROR
        elif level == "CRITICAL":
            _LOG_LEVEL = logging.CRITICAL
        else:
            raise ValueError("Unrecognized log level %s" % level)
    elif level not in [
        logging.DEBUG,
        logging.INFO,
        logging.WARNING,
        logging.ERROR,
        logging.CRITICAL,
    ]:
        raise ValueError("Unrecognized log level %s" % level)
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
