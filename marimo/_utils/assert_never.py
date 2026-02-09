# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any, NoReturn

from marimo import _loggers

LOGGER = _loggers.marimo_logger()


def _form_error_message(value: Any) -> str:
    return f"Unhandled value: {value} ({type(value).__name__})"


def assert_never(value: NoReturn) -> NoReturn:
    raise AssertionError(_form_error_message(value))


def log_never(value: NoReturn) -> None:
    LOGGER.warning(_form_error_message(value))
