# Copyright 2024 Marimo. All rights reserved.
import os
import shutil
from typing import List

from marimo._server.files.file_system import FileSystem
from marimo._server.models.files import FileInfo

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

                info = FileInfo(
                    id=entry.path,
                    path=entry.path,
                    name=entry.name,
                    is_directory=entry.is_dir(),
                    last_modified_date=entry.stat().st_mtime,
                )
                files.append(info)

        # Sort by directory first, then by name
        files.sort(key=lambda f: (not f.is_directory, f.name))

        return files

    def get_details(self, path: str) -> FileInfo:
        stat = os.stat(path)
        return FileInfo(
            id=path,
            path=path,
            name=os.path.basename(path),
            is_directory=os.path.isdir(path),
            last_modified_date=stat.st_mtime,
        )

    def open_file(self, path: str) -> str:
        with open(path, "r") as file:
            return file.read()

    def create_file_or_directory(
        self, path: str, file_type: str, name: str
    ) -> bool:
        full_path = os.path.join(path, name)
        try:
            if file_type == "directory":
                os.makedirs(full_path)
            else:
                with open(full_path, "w"):
                    pass  # Create an empty file
            return True
        except Exception:
            return False

    def delete_file_or_directory(self, path: str) -> bool:
        try:
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
            return True
        except Exception:
            return False

    def update_file_or_directory(self, path: str, new_path: str) -> bool:
        try:
            shutil.move(path, new_path)
            return True
        except Exception:
            return False
