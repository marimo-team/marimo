# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import NoReturn

from marimo import _loggers

LOGGER = _loggers.marimo_logger()


def assert_never(value: NoReturn) -> NoReturn:
    raise AssertionError(f"Unhandled value: {value} ({type(value).__name__})")


def log_never(value: NoReturn) -> None:
    LOGGER.warning("Unexpected value: %s (%s)", value, type(value).__name__)
    return value
