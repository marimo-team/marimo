# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Literal


def infer_package_manager() -> Literal["pip", "rye", "uv", "poetry", "pixi"]:
    """Infer the package manager from the current project."""

    try:
        # Get the project root by looking for common project files
        current_dir = Path.cwd()
        root_dir = current_dir

        while root_dir != root_dir.parent:
            if any(root_dir.glob("pyproject.toml")) or any(
                root_dir.glob("requirements.txt")
            ):
                break
            root_dir = root_dir.parent

        # Check for Poetry
        if (root_dir / "poetry.lock").exists():
            return "poetry"

        # Check for Rye
        if (root_dir / ".rye").exists():
            return "rye"

        # Check for Pixi
        if (root_dir / "pixi.toml").exists():
            return "pixi"

        VIRTUAL_ENV = os.environ.get("VIRTUAL_ENV", "")

        # Check for '/uv/' in VIRTUAL_ENV
        if (os.path.sep + "uv" + os.path.sep) in VIRTUAL_ENV:
            return "uv"

        # Check for virtualenv/pip
        if hasattr(sys, "real_prefix") or (
            hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix
        ):
            return "pip"

        # If no specific markers found, default to pip
        return "pip"
    except Exception:
        # Fallback to pip
        return "pip"
