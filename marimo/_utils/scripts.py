# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

# Moved to marimo._environments.script_metadata; re-exported for compatibility.
from marimo._environments.script_metadata import (
    REGEX,
    dumps as write_pyproject_to_script,
    loads as read_pyproject_from_script,
    with_python_version_requirement,
    wrap_block as wrap_script_metadata,
)

__all__ = [
    "REGEX",
    "read_pyproject_from_script",
    "with_python_version_requirement",
    "wrap_script_metadata",
    "write_pyproject_to_script",
]
