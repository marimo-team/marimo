from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class FileInfo:
    path: str
    name: str
    is_directory: bool
    size: Optional[int] = None  # Size in bytes for files, None for directories
    creation_date: Optional[str] = None  # Could be in ISO format
    last_modified_date: Optional[float] = None
    permissions: Optional[
        str
    ] = None  # Unix style permissions as a string, e.g., 'rwxr-xr-x'
    children: List["FileInfo"] = field(
        default_factory=list
    )  # Only populated for directories


@dataclass
class FileListRequest:
    path: str  # The directory path to list files from


@dataclass
class FileDetailsRequest:
    path: str  # The path of the file or directory


@dataclass
class FileOpenRequest:
    path: str  # The path of the file to open


@dataclass
class FileTreeRequest:
    path: str  # The root directory path for the tree


@dataclass
class FileCreateRequest:
    path: str  # The path where to create the file or directory
    type: str  # 'file' or 'directory'
    name: str  # The name of the file or directory


@dataclass
class FileDeleteRequest:
    path: str  # The path of the file or directory to delete


@dataclass
class FileUpdateRequest:
    path: str  # The current path of the file or directory
    new_path: str  # The new path or name for the file or directory


@dataclass
class FileListResponse:
    files: List[FileInfo]  # Reuse the FileInfo class defined earlier


@dataclass
class FileDetailsResponse:
    file: FileInfo  # Reuse the FileInfo class defined earlier


@dataclass
class FileOpenResponse:
    content: str  # The content of the file. For binary files, this might need to be encoded.


@dataclass
class FileTreeResponse:
    tree: FileInfo  # The root of the file tree, using FileInfo with children populated


@dataclass
class FileCreateResponse:
    success: bool
    message: Optional[
        str
    ] = None  # Additional information, e.g., error message


@dataclass
class FileDeleteResponse:
    success: bool
    message: Optional[
        str
    ] = None  # Additional information, e.g., error message


@dataclass
class FileUpdateResponse:
    success: bool
    message: Optional[
        str
    ] = None  # Additional information, e.g., error message
