# Copyright 2026 Marimo. All rights reserved.
"""Format handlers for different notebook file formats."""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Protocol

from marimo._ast import codegen
from marimo._convert.converters import MarimoConvert
from marimo._convert.markdown import convert_from_ir_to_markdown
from marimo._schemas.serialization import NotebookSerializationV1


class NotebookSerializer(Protocol):
    """Protocol for notebook format handlers."""

    def serialize(self, notebook: NotebookSerializationV1) -> str:
        """Convert notebook IR to the target format.

        Args:
            notebook: Notebook in intermediate representation
            path: Target file path
            previous_path: Previous file path (for format conversions)

        Returns:
            Serialized notebook content as string
        """
        ...

    def extract_header(self, path: Path) -> Optional[str]:
        """Extract header/metadata from an existing file.

        Args:
            path: File path to extract header from

        Returns:
            Header content or None
        """
        ...


class PythonNotebookSerializer(NotebookSerializer):
    """Handler for Python (.py) notebook files."""

    def serialize(self, notebook: NotebookSerializationV1) -> str:
        """Serialize notebook to Python format.

        Handles header preservation when converting from other formats.
        """
        contents = MarimoConvert.from_ir(notebook).to_py()

        return contents

    def extract_header(self, path: Path) -> Optional[str]:
        """Extract header comments from Python file."""
        return codegen.get_header_comments(path)


class MarkdownNotebookSerializer(NotebookSerializer):
    """Handler for Markdown (.md) notebook files."""

    def serialize(self, notebook: NotebookSerializationV1) -> str:
        """Serialize notebook to Markdown format."""
        return convert_from_ir_to_markdown(notebook)

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
