# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import base64
import mimetypes
import os
import re
import shutil
from typing import List, Literal, Optional, Union

from marimo._server.files.file_system import FileSystem
from marimo._server.models.files import FileDetailsResponse, FileInfo

IGNORE_LIST = [
    ".",
    "..",
    ".DS_Store",
    "__pycache__",
    "node_modules",
]

DISALLOWED_NAMES = [
    ".",
    "..",
]


class OSFileSystem(FileSystem):
    def get_root(self) -> str:
        return os.getcwd()

    def list_files(self, path: str) -> List[FileInfo]:
        files: List[FileInfo] = []
        folders: List[FileInfo] = []
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
        self, path: str, encoding: str | None = None
    ) -> FileDetailsResponse:
        file_info = self._get_file_info(path)
        contents = (
            self.open_file(path, encoding=encoding)
            if not file_info.is_directory
            else None
        )
        mime_type = mimetypes.guess_type(path)[0]
        return FileDetailsResponse(
            file=file_info, contents=contents, mime_type=mime_type
        )

    def _is_marimo_file(self, path: str) -> bool:
        if not path.endswith(".py"):
            return False

        with open(path, "rb") as file:
            return b"app = marimo.App(" in file.read()

    def open_file(self, path: str, encoding: str | None = None) -> str:
        try:
            with open(path, mode="r", encoding=encoding) as file:
                return file.read()
        except UnicodeDecodeError:
            # If its a UnicodeDecodeError, try as bytes and convert to base64
            with open(path, mode="rb") as file:
                return base64.b64encode(file.read()).decode("utf-8")

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

        full_path = os.path.join(path, name)
        # If the file already exists, generate a new name
        if os.path.exists(full_path):
            i = 1
            name_without_extension, extension = os.path.splitext(name)
            while True:
                new_name = f"{name_without_extension}_{i}{extension}"
                new_full_path = os.path.join(path, new_name)
                if not os.path.exists(new_full_path):
                    full_path = new_full_path
                    break
                i += 1

        if file_type == "directory":
            os.makedirs(full_path)
        else:
            with open(full_path, "wb") as file:
                if contents:
                    file.write(contents)
        # encoding latin-1 to get an invertible representation of the
        # bytes as a string ...
        return self.get_details(full_path, encoding="latin-1").file

    def delete_file_or_directory(self, path: str) -> bool:
        if os.path.isdir(path):
            shutil.rmtree(path)
        else:
            os.remove(path)
        return True

    def move_file_or_directory(self, path: str, new_path: str) -> FileInfo:
        file_name = os.path.basename(new_path)
        # Disallow renaming to . or ..
        if file_name in DISALLOWED_NAMES:
            raise ValueError(f"Cannot rename to {new_path}")

        shutil.move(path, new_path)
        return self.get_details(new_path).file

    def update_file(self, path: str, contents: str) -> FileInfo:
        with open(path, "w") as file:
            file.write(contents)
        return self.get_details(path).file


def natural_sort_file(file: FileInfo) -> List[Union[int, str]]:
    return natural_sort(file.name)


def natural_sort(filename: str) -> List[Union[int, str]]:
    def convert(text: str) -> Union[int, str]:
        return int(text) if text.isdigit() else text.lower()

    def alphanum_key(key: str) -> List[Union[int, str]]:
        return [convert(c) for c in re.split("([0-9]+)", key)]

    return alphanum_key(filename)
