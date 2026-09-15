# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo._cli.errors import MarimoCLIMissingDependencyError
from marimo._dependencies.dependencies import DependencyManager


def require_mcp_dependencies() -> None:
    dependency = DependencyManager.mcp
    if dependency.has_required_version(quiet=True):
        return

    if dependency.has(quiet=True):
        installed_version = dependency.get_version() or "unknown"
        message = (
            f"MCP SDK {installed_version} is not supported. "
            "marimo requires MCP >=2.0.0,<3.0.0."
        )
    else:
        message = "MCP dependencies not available."

    raise MarimoCLIMissingDependencyError(message, "marimo[mcp]")
