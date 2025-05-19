# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import abc
import os
import pathlib
import signal
from contextlib import contextmanager
from typing import TYPE_CHECKING, Optional

from marimo import _loggers
from marimo._config.config import SqlOutputType, WidthType
from marimo._server.api.status import HTTPException, HTTPStatus
from marimo._server.file_manager import AppFileManager
from marimo._server.files.os_file_system import natural_sort_file
from marimo._server.models.files import FileInfo
from marimo._server.models.home import MarimoFile
from marimo._utils.marimo_path import MarimoPath

if TYPE_CHECKING:
    from collections.abc import Generator
    from types import FrameType

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
            detail=f"Path {path} is not a valid file or directory",
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
    def from_files(files: list[MarimoFile]) -> AppFileRouter:
        return ListOfFilesAppFileRouter(files)

    @staticmethod
    def new_file() -> AppFileRouter:
        return NewFileAppFileRouter()

    def get_single_app_file_manager(
        self,
        default_width: WidthType | None = None,
        default_sql_output: SqlOutputType | None = None,
    ) -> AppFileManager:
        key = self.get_unique_file_key()
        assert key is not None, "Expected a single file"
        return self.get_file_manager(key, default_width, default_sql_output)

    def get_file_manager(
        self,
        key: MarimoFileKey,
        default_width: WidthType | None = None,
        default_sql_output: SqlOutputType | None = None,
    ) -> AppFileManager:
        """
        Given a key, return an AppFileManager.
        """
        if key.startswith(AppFileRouter.NEW_FILE):
            return AppFileManager(
                None,
                default_width=default_width,
                default_sql_output=default_sql_output,
            )

        if os.path.exists(key):
            return AppFileManager(
                key,
                default_width=default_width,
                default_sql_output=default_sql_output,
            )

        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"File {key} not found",
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
    def files(self) -> list[FileInfo]:
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
    def files(self) -> list[FileInfo]:
        return []


class ListOfFilesAppFileRouter(AppFileRouter):
    def __init__(self, files: list[MarimoFile]) -> None:
        self._files = files

    @property
    def files(self) -> list[FileInfo]:
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
        self._lazy_files: Optional[list[FileInfo]] = None

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
    def files(self) -> list[FileInfo]:
        if self._lazy_files is None:
            self._lazy_files = self._load_files()
        return self._lazy_files

    def _load_files(self) -> list[FileInfo]:
        import time

        start_time = time.time()
        MAX_EXECUTION_TIME = 5  # 5 seconds timeout

        def recurse(
            directory: str, depth: int = 0
        ) -> Optional[list[FileInfo]]:
            if depth > MAX_DEPTH:
                return None

            if time.time() - start_time > MAX_EXECUTION_TIME:
                raise HTTPException(
                    status_code=HTTPStatus.REQUEST_TIMEOUT,
                    detail="Request timed out: Loading workspace files took too long.",  # noqa: E501
                )

            try:
                entries = os.scandir(directory)
            except OSError as e:
                LOGGER.debug("OSError scanning directory: %s", str(e))
                return None

            files: list[FileInfo] = []
            folders: list[FileInfo] = []

            for entry in entries:
                # Skip hidden files and directories
                if entry.name.startswith("."):
                    continue

                if entry.is_dir():
                    if entry.name in skip_dirs or depth == MAX_DEPTH:
                        continue
                    children = recurse(entry.path, depth + 1)
                    if children:
                        folders.append(
                            FileInfo(
                                id=entry.path,
                                path=entry.path,
                                name=entry.name,
                                is_directory=True,
                                is_marimo_file=False,
                                children=children,
                            )
                        )
                elif entry.name.endswith(tuple(allowed_extensions)):
                    if self._is_marimo_app(entry.path):
                        files.append(
                            FileInfo(
                                id=entry.path,
                                path=entry.path,
                                name=entry.name,
                                is_directory=False,
                                is_marimo_file=True,
                                last_modified=entry.stat().st_mtime,
                            )
                        )

            # Sort folders then files, based on natural sort (alpha, then num)
            return sorted(folders, key=natural_sort_file) + sorted(
                files, key=natural_sort_file
            )

        MAX_DEPTH = 5
        skip_dirs = {
            "venv",
            "__pycache__",
            "node_modules",
            "site-packages",
            "eggs",
        }
        allowed_extensions = (
            (".py", ".md", ".qmd") if self.include_markdown else (".py",)
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


@contextmanager
def timeout(seconds: int, message: str) -> Generator[None, None, None]:
    def timeout_handler(signum: int, frame: Optional[FrameType]) -> None:
        del signum, frame
        raise HTTPException(
            status_code=HTTPStatus.REQUEST_TIMEOUT,
            detail=f"Request timed out: {message}",
        )

    # Set the timeout handler
    original_handler = signal.signal(signal.SIGALRM, timeout_handler)
    try:
        signal.alarm(seconds)
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, original_handler)
