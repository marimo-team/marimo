# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import TYPE_CHECKING

from marimo._utils.paths import normalize_path

if TYPE_CHECKING:
    from collections.abc import Iterator

NOTEBOOK_FILENAME: ContextVar[str | None] = ContextVar(
    "marimo_notebook_filename", default=None
)


@contextmanager
def notebook_filename(filename: str | None) -> Iterator[None]:
    """Track the notebook source during cell and pytest execution."""
    # Resolve before user code can change the working directory.
    filename = str(normalize_path(Path(filename))) if filename else None
    token = NOTEBOOK_FILENAME.set(filename)
    try:
        yield
    finally:
        NOTEBOOK_FILENAME.reset(token)
