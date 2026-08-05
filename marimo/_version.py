# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

_DISTRIBUTIONS = (
    "marimo",  # Standard installation
    "marimo-base",  # Slim distribution used by marimo.app
)


def _get_version() -> str:
    for distribution in _DISTRIBUTIONS:
        try:
            return version(distribution)
        except PackageNotFoundError:
            continue

    # package is not installed
    return "unknown"


__version__ = _get_version()
