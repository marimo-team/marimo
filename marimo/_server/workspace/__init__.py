# Copyright 2026 Marimo. All rights reserved.
"""Server-side notebook workspace abstractions.

A :class:`NotebookWorkspace` represents the set of notebooks a server is
hosting. Concrete subclasses cover:

- :class:`EmptyWorkspace` — untitled (``__new__``) notebook
- :class:`SingleFileWorkspace` — single notebook (``marimo edit nb.py``)
- :class:`FixedFilesWorkspace` — fixed allowlist (``marimo run a.py b.py``)
- :class:`DirectoryWorkspace` — lazy directory scan (``marimo edit ./``)
"""

import os

from marimo import _loggers
from marimo._server.workspace._base import (
    NEW_FILE,
    MarimoFileKey,
    NotebookWorkspace,
    count_files,
    flatten_files,
)
from marimo._server.workspace._directory import DirectoryWorkspace
from marimo._server.workspace._empty import EmptyWorkspace
from marimo._server.workspace._fixed import FixedFilesWorkspace
from marimo._server.workspace._single import SingleFileWorkspace
from marimo._utils.http import HTTPException, HTTPStatus
from marimo._utils.marimo_path import MarimoPath

LOGGER = _loggers.marimo_logger()


def infer_workspace(path: str) -> NotebookWorkspace:
    """Pick a concrete workspace for a user-supplied file or directory path."""
    if os.path.isfile(path):
        LOGGER.debug("Routing to file %s", path)
        return SingleFileWorkspace.from_path(MarimoPath(path))
    if os.path.isdir(path):
        LOGGER.debug("Routing to directory %s", path)
        return DirectoryWorkspace(path, include_markdown=False)
    raise HTTPException(
        status_code=HTTPStatus.BAD_REQUEST,
        detail=f"Path {path} is not a valid file or directory",
    )


__all__ = [
    "NEW_FILE",
    "DirectoryWorkspace",
    "EmptyWorkspace",
    "FixedFilesWorkspace",
    "MarimoFileKey",
    "NotebookWorkspace",
    "SingleFileWorkspace",
    "count_files",
    "flatten_files",
    "infer_workspace",
]
