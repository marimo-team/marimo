# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import Literal, Optional

import msgspec

from marimo._metadata.opengraph import OpenGraphMetadata
from marimo._server.models.models import BaseResponse


class FileInfo(msgspec.Struct, rename="camel"):
    """Metadata about a file or directory entry."""

    id: str
    path: str
    name: str
    is_directory: bool
    is_marimo_file: bool
    last_modified: Optional[float] = None
    children: list[FileInfo] = msgspec.field(default_factory=list)
    opengraph: OpenGraphMetadata | None = None


class FileListRequest(msgspec.Struct, rename="camel"):
    """Request to list files in a directory."""

    # The directory path to list files from
    # If None, the root directory will be used
    path: Optional[str] = None


class FileDetailsRequest(msgspec.Struct, rename="camel"):
    """Request for details about a specific file or directory."""

    # The path of the file or directory
    path: str


class FileOpenRequest(msgspec.Struct, rename="camel"):
    """Request to open a file in an external editor."""

    # The path of the file to open
    path: str
    line_number: Optional[int] = None


class FileTreeRequest(msgspec.Struct, rename="camel"):
    """Request to fetch a file tree rooted at the given path."""

    # The root directory path for the tree
    path: str


class FileCreateRequest(msgspec.Struct, rename="camel"):
    """Request to create a new file, directory, or notebook."""

    # The path where to create the file or directory
    path: str
    # 'file', 'directory', or 'notebook'
    type: Literal["file", "directory", "notebook"]
    # The name of the file or directory
    name: str
    # The contents of the file, base64-encoded
    contents: Optional[str] = None


class FileSearchRequest(msgspec.Struct, rename="camel"):
    """Request to search for files matching a query string."""

    # The search query string
    query: str
    # The root directory path to search from (optional, defaults to root)
    path: Optional[str] = None
    # Include directories
    include_directories: bool = True
    # Include files
    include_files: bool = True
    # Maximum depth to search (default: 3)
    depth: int = 3
    # Maximum number of results to return (default: 100)
    limit: int = 100


class FileDeleteRequest(msgspec.Struct, rename="camel"):
    """Request to delete a file or directory."""

    # The path of the file or directory to delete
    path: str


class FileMoveRequest(msgspec.Struct, rename="camel"):
    """Request to move or rename a file or directory."""

    # The current path of the file or directory
    path: str
    # The new path or name for the file or directory
    new_path: str


class FileUpdateRequest(msgspec.Struct, rename="camel"):
    """Request to update the contents of a file."""

    # The current path of the file or directory
    path: str
    # The new contents of the file
    contents: str


class FileListResponse(msgspec.Struct, rename="camel"):
    """Response containing a list of files and the filesystem root."""

    files: list[FileInfo]
    root: str


class FileDetailsResponse(msgspec.Struct, rename="camel"):
    """Response containing detailed information about a file."""

    file: FileInfo
    contents: Optional[str] = None
    mime_type: Optional[str] = None
    is_base64: bool = False


class FileCreateResponse(BaseResponse):
    """Response for a file creation request."""

    # Additional information, e.g., error message
    message: Optional[str] = None
    info: Optional[FileInfo] = None


class FileDeleteResponse(BaseResponse):
    """Response for a file deletion request."""

    # Additional information, e.g., error message
    message: Optional[str] = None


class FileUpdateResponse(BaseResponse):
    """Response for a file update request."""

    # Additional information, e.g., error message
    message: Optional[str] = None
    info: Optional[FileInfo] = None


class FileMoveResponse(BaseResponse):
    """Response for a file move/rename request."""

    # Additional information, e.g., error message
    message: Optional[str] = None
    info: Optional[FileInfo] = None


class FileSearchResponse(msgspec.Struct, rename="camel"):
    """Response containing search results."""

    files: list[FileInfo]
    query: str
    total_found: int
