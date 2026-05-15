# Copyright 2026 Marimo. All rights reserved.
"""Default-builders for boilerplate runtime test values."""

from __future__ import annotations

from typing import Any

from marimo._ast.app_config import _AppConfig
from marimo._runtime.commands import AppMetadata


def default_app_metadata(**overrides: Any) -> AppMetadata:
    """`AppMetadata` with empty defaults; overrides win."""
    base: dict[str, Any] = {
        "query_params": {},
        "filename": None,
        "cli_args": {},
        "argv": None,
        "app_config": _AppConfig(),
    }
    base.update(overrides)
    return AppMetadata(**base)
