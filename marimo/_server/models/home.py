from dataclasses import dataclass
from typing import List


@dataclass
class MarimoFile:
    # Name of the file
    name: str
    # Absolute path to the file
    path: str
    # Last modified time of the file
    last_modified: float


@dataclass
class RecentFilesResponse:
    files: List[MarimoFile]


@dataclass
class WorkspaceFilesResponse:
    files: List[MarimoFile]
