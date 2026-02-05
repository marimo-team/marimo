# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import os


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
