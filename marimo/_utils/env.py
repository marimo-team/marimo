# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import os
from typing import TypeVar, cast

from marimo import _loggers

LOGGER = _loggers.marimo_logger()

T = TypeVar("T", bound=str)


def env_choice(key: str, choices: tuple[T, ...], default: T) -> T:
    """Return the env var `key` constrained to one of `choices`.

    Comparison is case-insensitive and ignores surrounding whitespace. An unset
    variable returns `default`; an unrecognised one warns and returns `default`
    rather than raising, so a typo in a deployment's environment degrades to the
    documented behaviour instead of preventing the server from starting.
    """
    value = os.environ.get(key)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in choices:
        return cast("T", normalized)
    LOGGER.warning(
        "%s=%r is not one of %s; falling back to %r.",
        key,
        value,
        ", ".join(choices),
        default,
    )
    return default


def is_env_true(key: str, default: bool = False) -> bool:
    """Return True if the env var `key` is set to a truthy value ("true"/"1").

    Comparison is case-insensitive and ignores surrounding whitespace. Returns
    `default` when the variable is unset.
    """
    value = os.environ.get(key)
    if value is None:
        return default
    return value.strip().lower() in ("true", "1")


def env_to_value(key: str) -> tuple[str | None | list[str] | bool] | None:
    """Return a typed value from environment variables."""
    if key in os.environ:
        value = os.environ[key]
        if value.lower() in ("true", "false"):
            return (value.lower() == "true",)
        elif value.startswith("[") and value.endswith("]"):
            return (os.environ[key][1:-1].split(","),)
        elif value.lower() == "none":
            return None
        return (os.environ[key],)
    return None
