# Copyright 2024 Marimo. All rights reserved.
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class FileInfo:
    id: str
    path: str
    name: str
    is_directory: bool
    is_marimo_file: bool
    last_modified_date: Optional[float] = None
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
    type: str
    # The name of the file or directory
    name: str


@dataclass
class FileDeleteRequest:
    # The path of the file or directory to delete
    path: str


@dataclass
class FileUpdateRequest:
    # The current path of the file or directory
    path: str
    # The new path or name for the file or directory
    new_path: str


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
class FileCreateResponse:
    success: bool
    # Additional information, e.g., error message
    message: Optional[str] = None


@dataclass
class FileDeleteResponse:
    success: bool
    # Additional information, e.g., error message
    message: Optional[str] = None


@dataclass
class FileUpdateResponse:
    success: bool
    # Additional information, e.g., error message
    message: Optional[str] = None
