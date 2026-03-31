# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Union

if TYPE_CHECKING:
    import tempfile


def create_temp_notebook_file(
    name: str,
    extension: Literal["py", "md"],
    source: str,
    temp_dir: tempfile.TemporaryDirectory[str],
) -> MarimoPath:
    """Create a temporary notebook file with the given source content and return its MarimoPath."""
    fname = os.path.join(temp_dir.name, f"{name}.{extension}")
    path = MarimoPath(fname)
    path.write_text(source)
    return path


class MarimoPath:
    """
    Wrapper around pathlib.Path to provide additional functionality for Marimo.
    And reduce API surface area of pathlib.Path.
    """

    def __init__(self, path: Union[str, Path], strict: bool = False) -> None:
        self.path: Path = Path(path)
        # Do this on initialization to avoid issues with changing directories
        self.cwd = Path.cwd()
        # strict means can only operate in
        # anything under the current working directory
        self.strict = strict

        self.validate()

    def validate(self) -> None:
        """Raise ValueError if the path is not a valid Python or Markdown file."""
        if not self.is_valid():
            raise ValueError(
                f"File {self.path} is not a Python or Markdown file."
            )

    @staticmethod
    def is_valid_path(path: Union[str, Path]) -> bool:
        """Return True if the path can be wrapped in a MarimoPath without error."""
        try:
            MarimoPath(path)
            return True
        except ValueError:
            return False

    def is_valid(self) -> bool:
        """Return True if the path is a Python or Markdown file."""
        return self.is_python() or self.is_markdown()

    def is_python(self) -> bool:
        """Return True if the file has a .py extension."""
        return self.path.suffix == ".py"

    def is_markdown(self) -> bool:
        """Return True if the file has a .md, .markdown, or .qmd extension."""
        allowed = {".md", ".markdown", ".qmd"}
        return self.path.suffix in allowed

    def rename(self, new_path: Path) -> None:
        """Rename the file to new_path, enforcing strict mode constraints if enabled."""
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
        """Write text content to the file with the given encoding."""
        # By default, write as utf-8
        self.path.write_text(data, encoding)

    def read_text(self, encoding: str = "utf-8") -> str:
        """Read and return the file's text content."""
        return self.path.read_text(encoding)

    def read_bytes(self) -> bytes:
        """Read and return the file's raw bytes."""
        return self.path.read_bytes()

    @property
    def short_name(self) -> str:
        """The filename without directory components."""
        return self.path.name

    @property
    def relative_name(self) -> str:
        """The path relative to cwd, or the absolute path if outside cwd."""
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
        """Return True if this path is relative to (i.e., under) the given path."""
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
        """The absolute path as a string."""
        return str(self.path.absolute())

    @property
    def last_modified(self) -> float:
        """The file's last modification time as a Unix timestamp."""
        return self.path.stat().st_mtime

    def __str__(self) -> str:
        return str(self.path)
