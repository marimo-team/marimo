# Copyright 2024 Marimo. All rights reserved.
import mimetypes
import os
import shutil
from typing import List, Optional

from marimo._server.files.file_system import FileSystem
from marimo._server.models.files import FileDetailsResponse, FileInfo

IGNORE_LIST = [
    "__pycache__",
    "node_modules",
]

IGNORE_PREFIXES = [
    ".",
]


class OSFileSystem(FileSystem):
    def get_root(self) -> str:
        return os.getcwd()

    def list_files(self, path: str) -> List[FileInfo]:
        files: List[FileInfo] = []
        with os.scandir(path) as it:
            for entry in it:
                if entry.name in IGNORE_LIST:
                    continue
                if any(
                    entry.name.startswith(prefix) for prefix in IGNORE_PREFIXES
                ):
                    continue

                is_directory = entry.is_dir()
                info = FileInfo(
                    id=entry.path,
                    path=entry.path,
                    name=entry.name,
                    is_directory=is_directory,
                    is_marimo_file=not is_directory
                    and self._is_marimo_file(entry.path),
                    last_modified_date=entry.stat().st_mtime,
                )
                files.append(info)

        # Sort by directory first, then by name
        files.sort(key=lambda f: (not f.is_directory, f.name))

        return files

    def _get_file_info(self, path: str) -> FileInfo:
        stat = os.stat(path)
        is_directory = os.path.isdir(path)
        return FileInfo(
            id=path,
            path=path,
            name=os.path.basename(path),
            is_directory=is_directory,
            is_marimo_file=not is_directory and self._is_marimo_file(path),
            last_modified_date=stat.st_mtime,
        )

    def get_details(self, path: str) -> FileDetailsResponse:
        file_info = self._get_file_info(path)
        contents = self.open_file(path) if not file_info.is_directory else None
        mime_type = mimetypes.guess_type(path)[0]
        return FileDetailsResponse(
            file=file_info, contents=contents, mime_type=mime_type
        )

    def _is_marimo_file(self, path: str) -> bool:
        if not path.endswith(".py"):
            return False

        with open(path, "r") as file:
            return "app = marimo.App(" in file.read()

    def open_file(self, path: str) -> str:
        with open(path, "r") as file:
            return file.read()

    def create_file_or_directory(
        self,
        path: str,
        file_type: str,
        name: str,
        contents: Optional[str],
    ) -> FileInfo:
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
            with open(full_path, "w") as file:
                if contents:
                    file.write(contents)
        return self.get_details(full_path).file

    def delete_file_or_directory(self, path: str) -> bool:
        if os.path.isdir(path):
            shutil.rmtree(path)
        else:
            os.remove(path)
        return True

    def update_file_or_directory(self, path: str, new_path: str) -> FileInfo:
        shutil.move(path, new_path)
        return self.get_details(new_path).file
