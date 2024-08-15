# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Literal, Optional

from marimo._server.models.models import BaseResponse


@dataclass
class FileInfo:
    id: str
    path: str
    name: str
    is_directory: bool
    is_marimo_file: bool
    last_modified: Optional[float] = None
    children: List["FileInfo"] = field(default_factory=list)


@dataclass
class FileListRequest:
    # The directory path to list files from
    # If None, the root directory will be used
    path: Optional[str] = None


@dataclass
class FileDetailsRequest:
    # The path of the file or directory
    path: str


@dataclass
class FileOpenRequest:
    # The path of the file to open
    path: str


@dataclass
class FileTreeRequest:
    # The root directory path for the tree
    path: str


@dataclass
class FileCreateRequest:
    # The path where to create the file or directory
    path: str
    # 'file' or 'directory'
    type: Literal["file", "directory"]
    # The name of the file or directory
    name: str
    # The contents of the file, base64-encoded
    contents: Optional[str] = None


@dataclass
class FileDeleteRequest:
    # The path of the file or directory to delete
    path: str


@dataclass
class FileMoveRequest:
    # The current path of the file or directory
    path: str
    # The new path or name for the file or directory
    new_path: str


@dataclass
class FileUpdateRequest:
    # The current path of the file or directory
    path: str
    # The new contents of the file
    contents: str


@dataclass
class FileListResponse:
    files: List[FileInfo]
    root: str


@dataclass
class FileDetailsResponse:
    file: FileInfo
    contents: Optional[str] = None
    mime_type: Optional[str] = None


@dataclass
class FileCreateResponse(BaseResponse):
    # Additional information, e.g., error message
    message: Optional[str] = None
    info: Optional[FileInfo] = None


@dataclass
class FileDeleteResponse(BaseResponse):
    # Additional information, e.g., error message
    message: Optional[str] = None


@dataclass
class FileUpdateResponse(BaseResponse):
    # Additional information, e.g., error message
    message: Optional[str] = None
    info: Optional[FileInfo] = None


@dataclass
class FileMoveResponse(BaseResponse):
    # Additional information, e.g., error message
    message: Optional[str] = None
    info: Optional[FileInfo] = None
