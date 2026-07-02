# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


# Could be replaced with `find_uv_bin` from uv Python package in the future
def find_uv_bin() -> str:
    # Explicit override via environment variable
    from_env = os.environ.get("UV")
    if from_env:
        return from_env

    # Try to resolve via PATH
    resolved = shutil.which("uv")
    if resolved:
        return resolved

    # When the process has a limited PATH (e.g. launched from an IDE
    # extension or MCP client), check common install locations.
    candidates = [
        Path.home() / ".local" / "bin" / "uv",
        Path.home() / ".cargo" / "bin" / "uv",
        # Next to the running Python (works inside uv-managed venvs)
        Path(sys.executable).parent / "uv",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)

    # Fallback: bare name, let the OS resolve at call time.
    return "uv"
