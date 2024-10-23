# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from pathlib import Path


class MarimoPath:
    """
    Wrapper around pathlib.Path to provide additional functionality for Marimo.
    And reduce API surface area of pathlib.Path.
    """

    def __init__(self, path: str | Path, strict: bool = False) -> None:
        self.path: Path = Path(path)
        # Do this on initialization to avoid issues with changing directories
        self.cwd = Path.cwd()
        # strict means can only operate in
        # anything under the current working directory
        self.strict = strict

        self.validate()

    def validate(self) -> None:
        if not self.is_valid():
            raise ValueError(
                f"File {self.path} is not a Python or Markdown file."
            )

    @staticmethod
    def is_valid_path(path: str | Path) -> bool:
        try:
            MarimoPath(path)
            return True
        except ValueError:
            return False

    def is_valid(self) -> bool:
        return self.is_python() or self.is_markdown()

    def is_python(self) -> bool:
        return self.path.suffix == ".py"

    def is_markdown(self) -> bool:
        allowed = {".md", ".markdown", ".qmd"}
        return self.path.suffix in allowed

    def rename(self, new_path: Path) -> None:
        if self.strict:
            if not MarimoPath(new_path).is_relative_to(self.cwd):
                raise ValueError(
                    "Cannot rename files outside of "
                    "the current working directory"
                )

        # Cannot rename if already exists
        if new_path.exists():
            raise ValueError(
                f"Cannot rename {self.path} to {new_path}"
                " because it already exists"
            )

        self.path.rename(new_path)

    def write_text(self, data: str, encoding: str = "utf-8") -> None:
        # By default, write as utf-8
        self.path.write_text(data, encoding)

    def read_text(self, encoding: str = "utf-8") -> str:
        return self.path.read_text(encoding)

    @property
    def short_name(self) -> str:
        return self.path.name

    @property
    def relative_name(self) -> str:
        if self.strict:
            if not self.is_relative_to(self.cwd):
                raise ValueError(
                    "Cannot get relative name for files outside"
                    " of the current working directory"
                )
        # If can't return relative path, return absolute path
        if not self.is_relative_to(self.cwd):
            return str(self.path.absolute())
        return str(self.path.relative_to(self.cwd))

    def is_relative_to(self, other: Path) -> bool:
        # In python 3.8, is_relative_to is not available
        if not hasattr(self.path, "is_relative_to"):
            try:
                self.path.relative_to(other)
                return True
            except ValueError:
                return False
        return self.path.is_relative_to(other)  # type: ignore

    @property
    def absolute_name(self) -> str:
        return str(self.path.absolute())

    @property
    def last_modified(self) -> float:
        return self.path.stat().st_mtime

    def __str__(self) -> str:
        return str(self.path)
