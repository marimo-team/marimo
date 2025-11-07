# Copyright 2024 Marimo. All rights reserved.
"""Format handlers for different notebook file formats."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from marimo._ast import codegen
from marimo._convert.converters import MarimoConvert
from marimo._schemas.serialization import Header, NotebookSerializationV1


class NotebookSerializer(ABC):
    """Abstract base class for notebook format handlers."""

    @abstractmethod
    def serialize(
        self,
        notebook: NotebookSerializationV1,
        path: Path,
        previous_path: Optional[Path] = None,
    ) -> str:
        """Convert notebook IR to the target format.

        Args:
            notebook: Notebook in intermediate representation
            path: Target file path
            previous_path: Previous file path (for format conversions)

        Returns:
            Serialized notebook content as string
        """
        pass

    @abstractmethod
    def extract_header(self, path: Path) -> Optional[str]:
        """Extract header/metadata from an existing file.

        Args:
            path: File path to extract header from

        Returns:
            Header content or None
        """
        pass


class PythonNotebookSerializer(NotebookSerializer):
    """Handler for Python (.py) notebook files."""

    def serialize(
        self,
        notebook: NotebookSerializationV1,
        path: Path,
        previous_path: Optional[Path] = None,
    ) -> str:
        """Serialize notebook to Python format.

        Handles header preservation when converting from other formats.
        """
        # Path changed, extract headers from previous path
        if previous_path is not None and path.suffix != previous_path.suffix:
            prev_header = get_format_handler(previous_path).extract_header(
                previous_path
            )
            header_comments = prev_header
        else:
            header_comments = self.extract_header(path)

        # Convert to Python with headers
        contents = MarimoConvert.from_ir(
            NotebookSerializationV1(
                app=notebook.app,
                cells=notebook.cells,
                header=Header(value=header_comments or ""),
            )
        ).to_py()

        return contents

    def extract_header(self, path: Path) -> Optional[str]:
        """Extract header comments from Python file."""
        return codegen.get_header_comments(path)


class MarkdownNotebookSerializer(NotebookSerializer):
    """Handler for Markdown (.md) notebook files."""

    def serialize(
        self,
        notebook: NotebookSerializationV1,
        path: Path,
        previous_path: Optional[Path] = None,
    ) -> str:
        """Serialize notebook to Markdown format."""
        from marimo._server.export.exporter import Exporter

        contents, _ = Exporter().export_as_md(
            notebook,
            str(path),
            previous_path,
        )

        return contents

    def extract_header(self, path: Path) -> Optional[str]:
        """Extract YAML frontmatter from Markdown file."""
        from marimo._utils.inline_script_metadata import (
            get_headers_from_markdown,
        )

        markdown = path.read_text(encoding="utf-8")
        headers = get_headers_from_markdown(markdown)
        return headers.get("header", None) or headers.get("pyproject", None)


# Default format handlers
DEFAULT_FORMAT_HANDLERS = {
    ".py": PythonNotebookSerializer(),
    ".md": MarkdownNotebookSerializer(),
    ".qmd": MarkdownNotebookSerializer(),
}


def get_format_handler(path: Path) -> NotebookSerializer:
    """Get the appropriate format handler for a file.

    Args:
        path: File path

    Returns:
        Appropriate format handler

    Raises:
        ValueError: If no handler supports the file format
    """
    # Ensure path is a Path object
    if not isinstance(path, Path):
        path = Path(path)

    ext = path.suffix
    handler = DEFAULT_FORMAT_HANDLERS.get(ext)
    if handler is None:
        raise ValueError(
            f"No format handler found for {path}. Supported extensions: {list(DEFAULT_FORMAT_HANDLERS.keys())}"
        )
    return handler
