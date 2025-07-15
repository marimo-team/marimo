# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Literal, Optional

from marimo._utils.toml import read_toml

PackageManagerKind = Literal["pip", "rye", "uv", "poetry", "pixi"]


def infer_package_manager() -> PackageManagerKind:
    """Infer the package manager from the current project."""

    # `uv run` sets `UV` to the uv executable path
    # https://github.com/astral-sh/uv/issues/8775
    if os.environ.get("UV") is not None:
        return "uv"

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

        # If there is a pyproject.toml, try to infer the package manager
        pyproject_toml = root_dir / "pyproject.toml"
        if pyproject_toml.exists():
            package_manager = infer_package_manager_from_pyproject(
                pyproject_toml
            )
            if package_manager is not None:
                return package_manager

        # Try to infer from lockfiles
        package_manager = infer_package_manager_from_lockfile(root_dir)
        if package_manager is not None:
            return package_manager

        # misc - Check for pixi.toml
        if (root_dir / "pixi.toml").exists():
            return "pixi"

        # misc - Check for virtualenv/pip
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


def infer_package_manager_from_pyproject(
    pyproject_toml: Path,
) -> Optional[PackageManagerKind]:
    """Infer the package manager from a pyproject.toml file."""
    try:
        data = read_toml(pyproject_toml)

        if "tool" not in data:
            return None

        to_check: list[PackageManagerKind] = [
            "poetry",
            "pixi",
            "uv",
            "rye",
        ]

        for manager in to_check:
            if manager in data["tool"]:
                return manager

        return None
    except Exception:
        # Fallback to None
        return None


def infer_package_manager_from_lockfile(
    root_dir: Path,
) -> Optional[PackageManagerKind]:
    """Infer the package manager from a lockfile."""
    lockfile_map: dict[str, PackageManagerKind] = {
        "poetry.lock": "poetry",
        "pixi.lock": "pixi",
        ".uv": "uv",
        "requirements.lock": "rye",
    }
    try:
        for lockfile, manager in lockfile_map.items():
            if (root_dir / lockfile).exists():
                return manager
        return None
    except Exception:
        return None
