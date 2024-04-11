# Copyright 2024 Marimo. All rights reserved.
from dataclasses import dataclass
from typing import List, Optional

from marimo._server.ids import SessionId


@dataclass
class MarimoFile:
    # Name of the file
    name: str
    # Absolute path to the file
    path: str
    # Last modified time of the file
    last_modified: float
    # Session id
    session_id: Optional[SessionId] = None


@dataclass
class RecentFilesResponse:
    files: List[MarimoFile]


@dataclass
class WorkspaceFilesResponse:
    files: List[MarimoFile]


@dataclass
class ShutdownSessionRequest:
    session_id: SessionId
