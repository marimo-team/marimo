# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import abc
import os
import pathlib
from typing import List, Optional

from marimo import _loggers
from marimo._config.config import WidthType
from marimo._server.api.status import HTTPException, HTTPStatus
from marimo._server.file_manager import AppFileManager
from marimo._server.files.os_file_system import natural_sort_file
from marimo._server.models.files import FileInfo
from marimo._server.models.home import MarimoFile
from marimo._utils.marimo_path import MarimoPath

LOGGER = _loggers.marimo_logger()

# Some unique identifier for a file
MarimoFileKey = str


class AppFileRouter(abc.ABC):
    """
    Abstract class for routing files to an AppFileManager.
    """

    NEW_FILE: MarimoFileKey = "__new__"

    @property
    def directory(self) -> str | None:
        return None

    @staticmethod
    def infer(path: str) -> AppFileRouter:
        if os.path.isfile(path):
            LOGGER.debug("Routing to file %s", path)
            return AppFileRouter.from_filename(MarimoPath(path))
        if os.path.isdir(path):
            LOGGER.debug("Routing to directory %s", path)
            return AppFileRouter.from_directory(path)
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Path {0} is not a valid file or directory".format(path),
        )

    @staticmethod
    def from_filename(file: MarimoPath) -> AppFileRouter:
        files = [
            MarimoFile(
                name=file.relative_name,
                path=file.absolute_name,
                last_modified=file.last_modified,
            )
        ]
        return ListOfFilesAppFileRouter(files)

    @staticmethod
    def from_directory(directory: str) -> AppFileRouter:
        return LazyListOfFilesAppFileRouter(directory, include_markdown=False)

    @staticmethod
    def from_files(files: List[MarimoFile]) -> AppFileRouter:
        return ListOfFilesAppFileRouter(files)

    @staticmethod
    def new_file() -> AppFileRouter:
        return NewFileAppFileRouter()

    def get_single_app_file_manager(
        self, default_width: WidthType | None = None
    ) -> AppFileManager:
        key = self.get_unique_file_key()
        assert key is not None, "Expected a single file"
        return self.get_file_manager(key, default_width)

    def get_file_manager(
        self,
        key: MarimoFileKey,
        default_width: WidthType | None = None,
    ) -> AppFileManager:
        """
        Given a key, return an AppFileManager.
        """
        if key.startswith(AppFileRouter.NEW_FILE):
            return AppFileManager(None, default_width)

        for file in self.files:
            if file.path == key:
                return AppFileManager(file.path, default_width)

        path = (
            os.path.join(self.directory, key)
            if self.directory is not None
            else key
        )

        # Absolute path
        if os.path.isabs(path):
            return AppFileManager(path, default_width)

        # Relative path
        if os.path.exists(path):
            return AppFileManager(path, default_width)

        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="File {0} not found".format(key),
        )

    @abc.abstractmethod
    def get_unique_file_key(self) -> Optional[MarimoFileKey]:
        """
        If there is a unique file key, return it. Otherwise, return None.
        """
        pass

    @abc.abstractmethod
    def maybe_get_single_file(self) -> Optional[MarimoFile]:
        """
        If there is a single file, return it. Otherwise, return None.
        """
        pass

    @property
    @abc.abstractmethod
    def files(self) -> List[FileInfo]:
        """
        Get all files in a recursive tree.
        """
        pass


class NewFileAppFileRouter(AppFileRouter):
    def get_unique_file_key(self) -> Optional[MarimoFileKey]:
        return AppFileRouter.NEW_FILE

    def maybe_get_single_file(self) -> Optional[MarimoFile]:
        return None

    @property
    def files(self) -> List[FileInfo]:
        return []


class ListOfFilesAppFileRouter(AppFileRouter):
    def __init__(self, files: List[MarimoFile]) -> None:
        self._files = files

    @property
    def files(self) -> List[FileInfo]:
        return [
            FileInfo(
                id=file.path,
                name=file.name,
                path=file.path,
                last_modified=file.last_modified,
                is_directory=False,
                is_marimo_file=True,
            )
            for file in self._files
        ]

    def get_unique_file_key(self) -> Optional[MarimoFileKey]:
        if len(self.files) == 1:
            return self.files[0].path
        return None

    def maybe_get_single_file(self) -> Optional[MarimoFile]:
        if len(self.files) == 1:
            file = self.files[0]
            return MarimoFile(
                name=file.name,
                path=file.path,
                last_modified=file.last_modified,
            )
        return None


class LazyListOfFilesAppFileRouter(AppFileRouter):
    def __init__(self, directory: str, include_markdown: bool) -> None:
        # pass through Path to canonicalize, strips trailing slashes
        self._directory = str(pathlib.Path(directory))
        self.include_markdown = include_markdown
        self._lazy_files: Optional[List[FileInfo]] = None

    @property
    def directory(self) -> str:
        return self._directory

    def toggle_markdown(
        self, include_markdown: bool
    ) -> LazyListOfFilesAppFileRouter:
        # Only create a new instance if the include_markdown flag is different
        if include_markdown != self.include_markdown:
            return LazyListOfFilesAppFileRouter(
                self.directory, include_markdown
            )
        return self

    def mark_stale(self) -> None:
        self._lazy_files = None

    @property
    def files(self) -> List[FileInfo]:
        if self._lazy_files is None:
            self._lazy_files = self._load_files()
        return self._lazy_files

    def _load_files(self) -> List[FileInfo]:
        def recurse(
            directory: str, depth: int = 0
        ) -> Optional[List[FileInfo]]:
            if depth > MAX_DEPTH:
                return None

            try:
                entries = os.listdir(directory)
            except OSError as e:
                LOGGER.debug("OSError listing directory: %s", str(e))
                return None

            files: List[FileInfo] = []
            folders: List[FileInfo] = []
            for entry in entries:
                full_path = os.path.join(directory, entry)
                if os.path.isdir(full_path):
                    if entry in skip_dirs or depth == MAX_DEPTH:
                        continue
                    children = recurse(full_path, depth + 1)
                    if children:
                        folders.append(
                            FileInfo(
                                id=full_path,
                                path=full_path,
                                name=entry,
                                is_directory=True,
                                is_marimo_file=False,
                                children=children,
                            )
                        )
                else:
                    if any(
                        entry.endswith(ext) for ext in allowed_extensions
                    ) and self._is_marimo_app(full_path):
                        files.append(
                            FileInfo(
                                id=full_path,
                                path=full_path,
                                name=entry,
                                is_directory=False,
                                is_marimo_file=True,
                                last_modified=os.path.getmtime(full_path),
                            )
                        )
            # Sort folders then files, based on natural sort (alpha, then num)
            return sorted(folders, key=natural_sort_file) + sorted(
                files, key=natural_sort_file
            )

        MAX_DEPTH = 5
        skip_dirs = {".git", ".venv", "__pycache__", "node_modules"}
        allowed_extensions = (
            {".py", ".md"} if self.include_markdown else {".py"}
        )

        return recurse(self.directory) or []

    def _is_marimo_app(self, full_path: str) -> bool:
        try:
            path = MarimoPath(full_path)
            contents = path.read_text()
            if path.is_markdown():
                return "marimo-version:" in contents
            if path.is_python():
                return "marimo.App" in contents and "import marimo" in contents
            return False
        except Exception as e:
            LOGGER.debug("Error reading file %s: %s", full_path, e)
            return False

    def get_unique_file_key(self) -> str | None:
        return None

    def maybe_get_single_file(self) -> MarimoFile | None:
        return None
