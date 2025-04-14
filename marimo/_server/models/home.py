# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from marimo._server.models.files import FileInfo
from marimo._tutorials import Tutorial  # type: ignore
from marimo._types.ids import SessionId


@dataclass
class MarimoFile:
    # Name of the file
    name: str
    # Absolute path to the file
    path: str
    # Last modified time of the file
    last_modified: Optional[float] = None
    # Session id
    session_id: Optional[SessionId] = None
    # Session initialization id
    # This is the ID for when the session was initialized
    initialization_id: Optional[str] = None


@dataclass
class RecentFilesResponse:
    files: list[MarimoFile]


@dataclass
class RunningNotebooksResponse:
    files: list[MarimoFile]


@dataclass
class OpenTutorialRequest:
    tutorial_id: Tutorial


@dataclass
class WorkspaceFilesRequest:
    include_markdown: bool = False


@dataclass
class WorkspaceFilesResponse:
    root: str
    files: list[FileInfo]


@dataclass
class ShutdownSessionRequest:
    session_id: SessionId
