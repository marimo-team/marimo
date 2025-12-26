# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import base64
import mimetypes
import os
import platform
import re
import shutil
import subprocess
from collections import deque
from pathlib import Path
from typing import Literal, Optional, Union

from marimo import _loggers
from marimo._server.files.file_system import FileSystem
from marimo._server.models.files import FileDetailsResponse, FileInfo
from marimo._utils.files import natural_sort

LOGGER = _loggers.marimo_logger()

IGNORE_LIST = [
    ".",
    "..",
    ".DS_Store",
    "__pycache__",
    "node_modules",
    ".git",
    ".venv",
    "site-packages",
]

DISALLOWED_NAMES = [
    ".",
    "..",
]


class OSFileSystem(FileSystem):
    def get_root(self) -> str:
        return os.getcwd()

    def list_files(self, path: str) -> list[FileInfo]:
        files: list[FileInfo] = []
        folders: list[FileInfo] = []
        try:
            with os.scandir(path) as it:
                for entry in it:
                    if entry.name in IGNORE_LIST:
                        continue
                    try:
                        is_directory = entry.is_dir()
                        entry_stat = entry.stat()
                    except OSError:
                        # do not include files that fail to read
                        # (e.g. recursive/broken symlinks)
                        continue

                    info = FileInfo(
                        id=entry.path,
                        path=entry.path,
                        name=entry.name,
                        is_directory=is_directory,
                        is_marimo_file=not is_directory
                        and self._is_marimo_file(entry.path),
                        last_modified=entry_stat.st_mtime,
                    )
                    if is_directory:
                        folders.append(info)
                    else:
                        files.append(info)
        except OSError:
            pass

        return sorted(folders, key=natural_sort_file) + sorted(
            files, key=natural_sort_file
        )

    def _get_file_info(self, path: str) -> FileInfo:
        stat = os.stat(path)
        is_directory = os.path.isdir(path)
        return FileInfo(
            id=path,
            path=path,
            name=os.path.basename(path),
            is_directory=is_directory,
            is_marimo_file=not is_directory and self._is_marimo_file(path),
            last_modified=stat.st_mtime,
        )

    def get_details(
        self,
        path: str,
        encoding: str | None = None,
        contents: str | None = None,
    ) -> FileDetailsResponse:
        file_info = self._get_file_info(path)
        if file_info.is_directory:
            actual_contents = None
        elif contents is not None:
            actual_contents = contents
        else:
            actual_contents = self.open_file(path, encoding=encoding)
        mime_type = mimetypes.guess_type(path)[0]
        return FileDetailsResponse(
            file=file_info, contents=actual_contents, mime_type=mime_type
        )

    def _is_marimo_file(self, path: str) -> bool:
        file_path = Path(path)
        if not file_path.suffix == ".py":
            return False

        return b"app = marimo.App(" in file_path.read_bytes()

    def open_file(self, path: str, encoding: str | None = None) -> str:
        file_path = Path(path)
        try:
            return file_path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            # If its a UnicodeDecodeError, try as bytes and convert to base64
            return base64.b64encode(file_path.read_bytes()).decode("utf-8")

    def create_file_or_directory(
        self,
        path: str,
        file_type: Literal["file", "directory"],
        name: str,
        contents: Optional[bytes],
    ) -> FileInfo:
        if name in DISALLOWED_NAMES:
            raise ValueError(
                f"Cannot create file or directory with name {name}"
            )
        if name.strip() == "":
            raise ValueError("Cannot create file or directory with empty name")

        full_path = Path(path) / name
        # If the file already exists, generate a new name
        if full_path.exists():
            i = 1
            name_without_extension = full_path.stem
            extension = full_path.suffix
            while True:
                new_name = f"{name_without_extension}_{i}{extension}"
                new_full_path = full_path.parent / new_name
                if not new_full_path.exists():
                    full_path = new_full_path
                    break
                i += 1

        if file_type == "directory":
            full_path.mkdir(parents=True, exist_ok=True)
        else:
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_bytes(contents or b"")
        # encoding latin-1 to get an invertible representation of the
        # bytes as a string ...
        return self.get_details(
            str(full_path),
            encoding="latin-1",
            contents=(
                contents.decode("latin-1") if contents is not None else None
            ),
        ).file

    def delete_file_or_directory(self, path: str) -> bool:
        if os.path.isdir(path):
            safe_rmtree(path)
        else:
            os.remove(path)
        return True

    def move_file_or_directory(self, path: str, new_path: str) -> FileInfo:
        file_name = os.path.basename(new_path)
        # Disallow renaming to . or ..
        if file_name in DISALLOWED_NAMES:
            raise ValueError(f"Cannot rename to {new_path}")
        # Disallow moving to an existing path or directory
        if os.path.exists(new_path) or os.path.isdir(new_path):
            raise ValueError(
                f"Destination path {new_path} already exists or is a directory"
            )
        safe_move(path, new_path)
        return self.get_details(new_path).file

    def update_file(self, path: str, contents: str) -> FileInfo:
        file_path = Path(path)
        file_path.write_text(contents, encoding="utf-8")
        return self.get_details(path, contents=contents).file

    def search(
        self,
        query: str,
        *,
        path: Optional[str] = None,
        include_directories: bool = True,
        include_files: bool = True,
        depth: int = 3,
        limit: int = 100,
    ) -> list[FileInfo]:
        """Search for files and directories matching a query with high performance."""
        if not query.strip():
            return []

        search_path = path if path is not None else self.get_root()
        if not os.path.exists(search_path):
            return []

        # Compile regex pattern for case-insensitive search
        try:
            pattern = re.compile(re.escape(query.lower()))
        except re.error:
            # If regex compilation fails, fall back to simple string matching
            pattern = None

        results: list[FileInfo] = []
        seen_paths: set[str] = set()

        # Use BFS with deque for better performance than recursive DFS
        queue = deque([(search_path, 0)])  # (path, current_depth)

        while queue and len(results) < limit:
            current_path, current_depth = queue.popleft()

            # Skip if we've exceeded depth limit
            if current_depth > depth:
                continue

            # Skip if we've already processed this path (avoid symlink loops)
            if current_path in seen_paths:
                continue
            seen_paths.add(current_path)

            try:
                # Use os.scandir for better performance than os.listdir
                with os.scandir(current_path) as entries:
                    for entry in entries:
                        if len(results) >= limit:
                            break

                        # Skip ignored files/directories
                        if entry.name in IGNORE_LIST:
                            continue

                        # Check if name matches query
                        name_lower = entry.name.lower()
                        query_lower = query.lower()

                        matches = False
                        if pattern:
                            matches = pattern.search(name_lower) is not None
                        else:
                            matches = query_lower in name_lower

                        if not matches:
                            # If this is a directory and we haven't hit depth limit, add to queue
                            if current_depth < depth:
                                try:
                                    if entry.is_dir():
                                        queue.append(
                                            (entry.path, current_depth + 1)
                                        )
                                except OSError:
                                    # Skip entries that can't be accessed
                                    continue
                            continue

                        try:
                            is_directory = entry.is_dir()
                            entry_stat = entry.stat()

                            # Apply directory/file filtering
                            if not include_directories and is_directory:
                                # Skip directories if directory=False
                                continue
                            if not include_files and not is_directory:
                                # Skip files if file=False
                                continue

                            file_info = FileInfo(
                                id=entry.path,
                                path=entry.path,
                                name=entry.name,
                                is_directory=is_directory,
                                # This can be expensive, so we don't do it on search
                                is_marimo_file=False,
                                last_modified=entry_stat.st_mtime,
                            )
                            results.append(file_info)

                            # If this is a matching directory and we haven't hit depth limit, add to queue
                            if is_directory and current_depth < depth:
                                queue.append((entry.path, current_depth + 1))

                        except OSError:
                            # Skip files/directories that can't be accessed
                            continue

            except OSError:
                # Skip directories that can't be accessed
                continue

        # Sort results by relevance (exact matches first, then by name)
        def sort_key(file_info: FileInfo) -> tuple[int, str]:
            name_lower = file_info.name.lower()
            query_lower = query.lower()

            # Exact match gets highest priority
            if name_lower == query_lower:
                return (0, file_info.name)
            # Starts with query gets second priority
            elif name_lower.startswith(query_lower):
                return (1, file_info.name)
            # Contains query gets lowest priority
            else:
                return (2, file_info.name)

        results.sort(key=sort_key)
        return results[:limit]

    def open_in_editor(self, path: str, line_number: int | None) -> bool:
        try:
            # First try to get editor from environment variable
            editor = os.environ.get("EDITOR")

            # If editor is a terminal-based editor, we just call `open`, because
            # otherwise it silently opens the terminal in the same window that is
            # running marimo.
            if editor and not _is_terminal_editor(editor):
                args = (
                    [path]
                    if line_number is None
                    else editor_open_file_in_line_args(
                        editor, path, line_number
                    )
                )

                try:
                    # For GUI editors
                    subprocess.run([editor, *args])
                    return True
                except Exception as e:
                    LOGGER.error(f"Error opening with EDITOR: {e}")
                    pass

            # Use system default if no editor specified
            if platform.system() == "Darwin":  # macOS
                subprocess.call(("open", path))
            elif platform.system() == "Windows":  # Windows
                # startfile only exists on Windows
                os.startfile(path)  # type: ignore[attr-defined]
            else:  # Linux variants
                subprocess.call(("xdg-open", path))
            return True
        except Exception as e:
            LOGGER.error(f"Error opening file: {e}")
            return False


def editor_open_file_in_line_args(
    editor: str, path: str, line_number: int
) -> list[str]:
    if editor == "code":
        return ["--goto", f"{path}:{line_number}"]
    elif editor == "subl":
        return [f"{path}:{line_number}"]
    else:
        return [f"+{line_number}", path]


def natural_sort_file(file: FileInfo) -> list[Union[int, str]]:
    return natural_sort(file.name)


def _is_terminal_editor(editor: str) -> bool:
    return any(
        ed in editor.lower()
        for ed in [
            "vim",
            "vi",
            "emacs",
            "nano",
            "nvim",
            "neovim",
            "pico",
            "micro",
        ]
    )


def safe_rmtree(path: str) -> None:
    """
    Remove a directory tree. If shutil.rmtree fails, recursively delete all files from the leaves up.

    This is so we can be compatible with https://github.com/awslabs/mountpoint-s3.
    """
    try:
        shutil.rmtree(path)
    except PermissionError:
        # Fallback: manual post-order traversal
        p = Path(path)
        for sub in sorted(
            p.rglob("*"), key=lambda x: -x.as_posix().count("/")
        ):
            try:
                if sub.is_file() or sub.is_symlink():
                    sub.unlink()
                elif sub.is_dir():
                    sub.rmdir()
            except Exception as inner_e:
                LOGGER.warning("Failed to delete %s: %s", sub, inner_e)
        try:
            p.rmdir()
        except Exception as final_e:
            LOGGER.warning("Failed to delete directory %s: %s", p, final_e)


def safe_move(src: str, dst: str) -> None:
    """
    Move a file or directory, but if it fails due to permissions,
    copy the file or directory and then delete the original.

    This is so we can be compatible with https://github.com/awslabs/mountpoint-s3.
    """
    try:
        shutil.move(src, dst)
    except PermissionError:
        # Fallback: copy then delete
        src_path = Path(src)
        if src_path.is_dir():
            shutil.copytree(src, dst)
            safe_rmtree(src)
        else:
            shutil.copy2(src, dst)
            src_path.unlink()
