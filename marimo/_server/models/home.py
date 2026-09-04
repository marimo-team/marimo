# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import msgspec

from marimo._server.models.files import FileInfo
from marimo._tutorials import Tutorial  # type: ignore
from marimo._types.ids import SessionId


class MarimoFile(msgspec.Struct, rename="camel"):
    # Name of the file
    name: str
    # Absolute path to the file
    path: str
    # Last modified time of the file
    last_modified: float | None = None
    # Session id
    session_id: SessionId | None = None
    # Session initialization id
    # This is the ID for when the session was initialized
    initialization_id: str | None = None


class RecentFilesResponse(msgspec.Struct, rename="camel"):
    files: list[MarimoFile]


class RunningNotebooksResponse(msgspec.Struct, rename="camel"):
    files: list[MarimoFile]


class OpenTutorialRequest(msgspec.Struct, rename="camel"):
    tutorial_id: Tutorial


class WorkspaceFilesRequest(msgspec.Struct, rename="camel"):
    include_markdown: bool = False


class WorkspaceFilesResponse(msgspec.Struct, rename="camel"):
    root: str
    files: list[FileInfo]
    # Indicates the listing is incomplete: a file count, depth, or time limit
    # was reached while scanning, so some files or folders were left out
    has_more: bool = False
    # Total files found
    file_count: int = 0


class ShutdownSessionRequest(msgspec.Struct, rename="camel"):
    session_id: SessionId
