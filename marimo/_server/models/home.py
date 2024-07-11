# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from marimo._server.ids import SessionId
from marimo._server.models.files import FileInfo


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
    files: List[MarimoFile]


@dataclass
class RunningNotebooksResponse:
    files: List[MarimoFile]


@dataclass
class WorkspaceFilesRequest:
    include_markdown: bool = False


@dataclass
class WorkspaceFilesResponse:
    root: str
    files: List[FileInfo]


@dataclass
class ShutdownSessionRequest:
    session_id: SessionId
