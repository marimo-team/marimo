# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import os
import pathlib
from dataclasses import dataclass, field
from typing import List

from marimo import _loggers
from marimo._server.models.home import MarimoFile
from marimo._utils.config.config import ConfigReader
from marimo._utils.paths import pretty_path


@dataclass
class RecentFilesState:
    files: List[str] = field(default_factory=list)


# TODO(akshayka): _IGNORED_FOLDERS doesn't cover Windows
_IGNORED_FOLDERS = ("/tmp", "/var")

LOGGER = _loggers.marimo_logger()


def _is_tmp_file(filename: str) -> bool:
    return any(
        filename.startswith(folder_name) for folder_name in _IGNORED_FOLDERS
    )


class RecentFilesManager:
    MAX_FILES = 5
    LOCATION = "recent_files.toml"

    def __init__(self) -> None:
        self.config = ConfigReader.for_filename(self.LOCATION)

    def touch(self, filename: str) -> None:
        if not self.config:
            return

        if _is_tmp_file(filename):
            return

        try:
            state = self.config.read_toml(
                RecentFilesState, fallback=RecentFilesState()
            )
        except Exception as e:
            LOGGER.error("Failed to read recent notebook at %s", self.LOCATION)
            LOGGER.error(str(e))
            # On error we overwrite the corrupted recents file; nothing
            # of significance is lost
            state = RecentFilesState()

        if filename in state.files:
            state.files.remove(filename)
        state.files.insert(0, filename)
        state.files = state.files[: self.MAX_FILES]

        try:
            self.config.write_toml(state)
        except Exception as e:
            LOGGER.error(
                "Failed to write recent notebook at %s", self.LOCATION
            )
            LOGGER.error(str(e))

    def rename(self, old_filename: str, new_filename: str) -> None:
        if not self.config:
            return

        state = self.config.read_toml(
            RecentFilesState, fallback=RecentFilesState()
        )
        if old_filename in state.files:
            state.files.remove(old_filename)
            state.files.insert(0, new_filename)
            state.files = state.files[: self.MAX_FILES]

            self.config.write_toml(state)

    def get_recents(self) -> List[MarimoFile]:
        if not self.config:
            return []

        state = self.config.read_toml(
            RecentFilesState, fallback=RecentFilesState()
        )
        files: List[MarimoFile] = []

        cwd = pathlib.Path.cwd()
        limited_files = state.files[: self.MAX_FILES]
        for file in limited_files:
            file_path = pathlib.Path(file)
            if _is_tmp_file(file) or cwd not in file_path.parents:
                continue
            if not os.path.exists(file):
                continue
            files.append(
                MarimoFile(
                    name=os.path.basename(file),
                    path=pretty_path(file),
                    last_modified=os.path.getmtime(file),
                )
            )

        return files
