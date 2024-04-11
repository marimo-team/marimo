# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import abc
import os
from typing import List, Optional

from marimo import _loggers
from marimo._server.api.status import HTTPException, HTTPStatus
from marimo._server.file_manager import AppFileManager
from marimo._server.models.home import MarimoFile

LOGGER = _loggers.marimo_logger()

# Some unique identifier for a file
MarimoFileKey = str


class AppFileRouter(abc.ABC):
    """
    Abstract class for routing files to an AppFileManager.
    """

    NEW_FILE: MarimoFileKey = "__new__"

    @staticmethod
    def infer(path: str) -> AppFileRouter:
        if os.path.isfile(path):
            LOGGER.debug("Routing to file %s", path)
            return AppFileRouter.from_filename(path)
        if os.path.isdir(path):
            LOGGER.debug("Routing to directory %s", path)
            return AppFileRouter.from_directory(path)
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Path {0} is not a valid file or directory".format(path),
        )

    @staticmethod
    def from_filename(filename: str) -> AppFileRouter:
        files = [
            MarimoFile(
                name=filename,
                path=os.path.abspath(filename),
                last_modified=os.path.getmtime(filename),
            )
        ]
        return ListOfFilesAppFileRouter(files)

    @staticmethod
    def from_directory(directory: str) -> AppFileRouter:
        return LazyListOfFilesAppFileRouter(directory)

    @staticmethod
    def from_files(files: List[MarimoFile]) -> AppFileRouter:
        return ListOfFilesAppFileRouter(files)

    @staticmethod
    def new_file() -> AppFileRouter:
        return NewFileAppFileRouter()

    def get_single_app_file_manager(self) -> AppFileManager:
        key = self.get_unique_file_key()
        assert key is not None, "Expected a single file"
        return self.get_file_manager(key)

    def get_file_manager(self, key: MarimoFileKey) -> AppFileManager:
        """
        Given a key, return an AppFileManager.
        """
        if key == AppFileRouter.NEW_FILE:
            return AppFileManager(None)

        for file in self.files:
            if file.path == key:
                return AppFileManager(file.path)

        # Absolute path
        if os.path.isabs(key):
            return AppFileManager(key)

        # Relative path
        if os.path.exists(key):
            return AppFileManager(key)

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
    def files(self) -> List[MarimoFile]:
        """
        Get all files.
        """
        pass


class NewFileAppFileRouter(AppFileRouter):
    def get_unique_file_key(self) -> Optional[MarimoFileKey]:
        return AppFileRouter.NEW_FILE

    def maybe_get_single_file(self) -> Optional[MarimoFile]:
        return None

    @property
    def files(self) -> List[MarimoFile]:
        return []


class ListOfFilesAppFileRouter(AppFileRouter):
    def __init__(self, files: List[MarimoFile]) -> None:
        self._files = files

    @property
    def files(self) -> List[MarimoFile]:
        return self._files

    def get_unique_file_key(self) -> Optional[MarimoFileKey]:
        if len(self.files) == 1:
            return self.files[0].path
        return None

    def maybe_get_single_file(self) -> Optional[MarimoFile]:
        if len(self.files) == 1:
            return self.files[0]
        return None


class LazyListOfFilesAppFileRouter(AppFileRouter):
    def __init__(self, directory: str) -> None:
        self.directory = directory
        self._lazy_files: Optional[List[MarimoFile]] = None

    @property
    def files(self) -> List[MarimoFile]:
        if self._lazy_files is None:
            self._lazy_files = self._load_files()
        return self._lazy_files

    def _load_files(self) -> List[MarimoFile]:
        directory = self.directory
        # Recursively find all .py files that contain the string "marimo.App"
        # Max depth of 5 to avoid searching the entire filesystem
        MAX_DEPTH = 5
        files: List[MarimoFile] = []
        skip_dirs = {".git", ".venv", "__pycache__", "node_modules"}
        LOGGER.debug("Searching directory %s", directory)
        for root, _, filenames in os.walk(directory, topdown=True):
            # Skip directories that are too deep
            depth = root[len(directory) :].count(os.sep)
            if depth > MAX_DEPTH:
                continue
            # Skip directories that we don't want to search
            root_name = os.path.basename(root)
            if root_name in skip_dirs:
                continue
            # Iterate over all files in the directory
            for filename in filenames:
                if not filename.endswith(".py"):
                    continue
                full_path = os.path.join(root, filename)
                relative_path = os.path.relpath(full_path, directory)
                with open(full_path, "r", encoding="utf-8") as f:
                    if "marimo.App" in f.read():
                        files.append(
                            MarimoFile(
                                name=filename,
                                path=relative_path,
                                last_modified=os.path.getmtime(full_path),
                            )
                        )
        LOGGER.debug("Found %d files in directory %s", len(files), directory)
        return files

    def get_unique_file_key(self) -> str | None:
        return None

    def maybe_get_single_file(self) -> MarimoFile | None:
        return None
