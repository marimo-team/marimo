# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import Literal

import msgspec

from marimo._metadata.opengraph import OpenGraphMetadata
from marimo._server.models.models import BaseResponse


class FileInfo(msgspec.Struct, rename="camel"):
    id: str
    path: str
    name: str
    is_directory: bool
    is_marimo_file: bool
    last_modified: float | None = None
    children: list[FileInfo] = msgspec.field(default_factory=list)
    opengraph: OpenGraphMetadata | None = None


class FileListRequest(msgspec.Struct, rename="camel"):
    # The directory path to list files from
    # If None, the root directory will be used
    path: str | None = None


class FileDetailsRequest(msgspec.Struct, rename="camel"):
    # The path of the file or directory
    path: str


class FileOpenRequest(msgspec.Struct, rename="camel"):
    # The path of the file to open
    path: str
    line_number: int | None = None


class FileTreeRequest(msgspec.Struct, rename="camel"):
    # The root directory path for the tree
    path: str


class FileCreateRequest(msgspec.Struct, rename="camel"):
    # The path where to create the file or directory
    path: str
    # 'file', 'directory', or 'notebook'
    type: Literal["file", "directory", "notebook"]
    # The name of the file or directory
    name: str
    # The contents of the file, base64-encoded
    contents: str | None = None


class FileSearchRequest(msgspec.Struct, rename="camel"):
    # The search query string
    query: str
    # The root directory path to search from (optional, defaults to root)
    path: str | None = None
    # Include directories
    include_directories: bool = True
    # Include files
    include_files: bool = True
    # Maximum depth to search (default: 3)
    depth: int = 3
    # Maximum number of results to return (default: 100)
    limit: int = 100


class FileDeleteRequest(msgspec.Struct, rename="camel"):
    # The path of the file or directory to delete
    path: str


class FileMoveRequest(msgspec.Struct, rename="camel"):
    # The current path of the file or directory
    path: str
    # The new path or name for the file or directory
    new_path: str


class FileUpdateRequest(msgspec.Struct, rename="camel"):
    # The current path of the file or directory
    path: str
    # The new contents of the file
    contents: str


class FileListResponse(msgspec.Struct, rename="camel"):
    files: list[FileInfo]
    root: str


class FileDetailsResponse(msgspec.Struct, rename="camel"):
    file: FileInfo
    contents: str | None = None
    mime_type: str | None = None
    is_base64: bool = False


class FileCreateResponse(BaseResponse):
    # Additional information, e.g., error message
    message: str | None = None
    info: FileInfo | None = None


class FileDeleteResponse(BaseResponse):
    # Additional information, e.g., error message
    message: str | None = None


class FileUpdateResponse(BaseResponse):
    # Additional information, e.g., error message
    message: str | None = None
    info: FileInfo | None = None


class FileMoveResponse(BaseResponse):
    # Additional information, e.g., error message
    message: str | None = None
    info: FileInfo | None = None


class FileSearchResponse(msgspec.Struct, rename="camel"):
    files: list[FileInfo]
    query: str
    total_found: int
