# Copyright 2026 Marimo. All rights reserved.
"""Pytest fixtures for _ast tests."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Optional

import pytest

from marimo._ast.app import App
from marimo._ast.parse import MarimoFileError


def _dynamic_load(filename: str | Path) -> Optional[App]:
    """Create and execute a module with the provided filename.

    Test utility for backward compatibility testing. Not for production use.
    """
    if filename is None:
        return None

    path = Path(filename)
    contents = (
        path.read_text(encoding="utf-8").strip() if path.exists() else None
    )
    if not contents:
        return None

    spec = importlib.util.spec_from_file_location("marimo_app", filename)
    if spec is None:
        raise RuntimeError("Failed to load module spec")
    marimo_app = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        raise RuntimeError("Failed to load module spec's loader")
    try:
        sys.modules["marimo_app"] = marimo_app
        spec.loader.exec_module(marimo_app)
    finally:
        sys.modules.pop("marimo_app", None)
    if not hasattr(marimo_app, "app"):
        return None
    if not isinstance(marimo_app.app, App):
        raise MarimoFileError("`app` attribute must be of type `marimo.App`.")

    return marimo_app.app


@pytest.fixture
def dynamic_load():
    """Direct dynamic load for backward compatibility testing."""
    return _dynamic_load
