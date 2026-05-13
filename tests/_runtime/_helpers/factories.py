# Copyright 2026 Marimo. All rights reserved.
"""Default-builders for the boilerplate values tests inline today."""

from __future__ import annotations

from typing import Any

from marimo._ast.app_config import _AppConfig
from marimo._config.config import DEFAULT_CONFIG, MarimoConfig
from marimo._runtime.commands import AppMetadata


def default_app_metadata(**overrides: Any) -> AppMetadata:
    """`AppMetadata` with empty defaults; overrides win.

    Replaces inline `AppMetadata(query_params={}, filename=None, cli_args={}, ...)`
    construction at the dozens of test sites that just need defaults.
    """
    base: dict[str, Any] = {
        "query_params": {},
        "filename": None,
        "cli_args": {},
        "argv": None,
        "app_config": _AppConfig(),
    }
    base.update(overrides)
    return AppMetadata(**base)


def default_user_config(**overrides: Any) -> MarimoConfig:
    """Copy of `DEFAULT_CONFIG` with deep-merge-ish overrides at the top level."""
    config: MarimoConfig = DEFAULT_CONFIG.copy()  # type: ignore[assignment]
    for key, value in overrides.items():
        config[key] = value  # type: ignore[literal-required]
    return config
