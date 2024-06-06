# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import abc
import os
from typing import List, Optional

from marimo import _loggers
from marimo._config.config import WidthType
from marimo._server.api.status import HTTPException, HTTPStatus
from marimo._server.file_manager import AppFileManager
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

        # Absolute path
        if os.path.isabs(key):
            return AppFileManager(key, default_width)

        # Relative path
        if os.path.exists(key):
            return AppFileManager(key, default_width)

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
    def __init__(self, directory: str, include_markdown: bool) -> None:
        self.directory = directory
        self.include_markdown = include_markdown
        self._lazy_files: Optional[List[MarimoFile]] = None

    def toggle_markdown(
        self, include_markdown: bool
    ) -> LazyListOfFilesAppFileRouter:
        # Only create a new instance if the include_markdown flag is different
        if include_markdown != self.include_markdown:
            return LazyListOfFilesAppFileRouter(
                self.directory, include_markdown
            )
        return self

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
        allowed_extensions = (
            {".py", ".md"} if self.include_markdown else {".py"}
        )

        LOGGER.debug("Searching directory %s", directory)
        cwd = os.getcwd()
        for root, dirnames, filenames in os.walk(directory, topdown=True):
            # Skip directories that are too deep
            depth = root[len(directory) :].count(os.sep)
            if depth >= MAX_DEPTH:
                # mutating `dirnames` like this prunes all the dirs in it
                # from the search
                dirnames[:] = []
                continue
            # Skip directories that we don't want to search
            root_name = os.path.basename(root)
            if root_name in skip_dirs:
                continue
            # Iterate over all files in the directory
            for filename in filenames:
                if not any(
                    filename.endswith(ext) for ext in allowed_extensions
                ):
                    continue
                full_path = os.path.join(root, filename)
                shortest_path = (
                    os.path.relpath(full_path, cwd)
                    if full_path.startswith(cwd)
                    else full_path
                )
                # Python files must contain "marimo.App", or markdown files
                if self._is_marimo_app(full_path):
                    files.append(
                        MarimoFile(
                            name=filename,
                            path=shortest_path,
                            last_modified=os.path.getmtime(full_path),
                        )
                    )
        LOGGER.debug("Found %d files in directory %s", len(files), directory)
        return files

    def _is_marimo_app(self, full_path: str) -> bool:
        try:
            path = MarimoPath(full_path)
            contents = path.read_text()
            if path.is_markdown():
                return "marimo-version:" in contents
            if path.is_python():
                return "marimo.App" in contents
            return False
        except Exception as e:
            LOGGER.debug("Error reading file %s: %s", full_path, e)
            return False

    def get_unique_file_key(self) -> str | None:
        return None

    def maybe_get_single_file(self) -> MarimoFile | None:
        return None
