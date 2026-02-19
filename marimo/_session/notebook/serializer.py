# Copyright 2026 Marimo. All rights reserved.
"""Format handlers for different notebook file formats."""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Protocol

from marimo._schemas.serialization import (
    AppInstantiation,
    NotebookSerializationV1,
)


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

    def deserialize(
        self, content: str, filepath: Optional[str] = None
    ) -> NotebookSerializationV1:
        """Convert content string to notebook IR.

        Args:
            content: File content as string
            filepath: Optional file path for error reporting

        Returns:
            Notebook in intermediate representation
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
        from marimo._ast.codegen import generate_filecontents_from_ir

        return generate_filecontents_from_ir(notebook)

    def deserialize(
        self, content: str, filepath: Optional[str] = None
    ) -> NotebookSerializationV1:
        """Deserialize Python notebook content to IR."""
        from marimo._ast.parse import parse_notebook

        notebook = parse_notebook(content, filepath=filepath or "<marimo>")
        return notebook or NotebookSerializationV1(
            app=AppInstantiation(options={}), filename=filepath
        )

    def extract_header(self, path: Path) -> Optional[str]:
        """Extract header comments from Python file."""
        from marimo._ast.codegen import get_header_comments

        return get_header_comments(path)


class MarkdownNotebookSerializer(NotebookSerializer):
    """Handler for Markdown (.md) notebook files."""

    def serialize(self, notebook: NotebookSerializationV1) -> str:
        """Serialize notebook to Markdown format."""
        from marimo._convert.markdown import convert_from_ir_to_markdown

        return convert_from_ir_to_markdown(notebook)

    def deserialize(
        self, content: str, filepath: Optional[str] = None
    ) -> NotebookSerializationV1:
        """Deserialize Markdown notebook content to IR."""
        from marimo._convert.markdown.to_ir import convert_from_md_to_marimo_ir

        return convert_from_md_to_marimo_ir(content, filepath=filepath)

    def extract_header(self, path: Path) -> Optional[str]:
        """Extract full frontmatter metadata from Markdown file as YAML.

        Unlike Python files where only the script preamble matters, markdown
        frontmatter can carry arbitrary metadata (author, description, tags,
        etc.) that must survive through the save lifecycle. Return the full
        frontmatter as YAML so _save_file() preserves it all.
        """
        from marimo._convert.markdown.to_ir import extract_frontmatter
        from marimo._utils import yaml

        markdown = path.read_text(encoding="utf-8")
        frontmatter, _ = extract_frontmatter(markdown)
        if not frontmatter:
            return None
        return yaml.dump(frontmatter, sort_keys=False)


# Default format handlers
DEFAULT_NOTEBOOK_SERIALIZERS = {
    ".py": PythonNotebookSerializer(),
    ".md": MarkdownNotebookSerializer(),
    ".qmd": MarkdownNotebookSerializer(),
}


def get_notebook_serializer(path: Path) -> NotebookSerializer:
    """Get the appropriate notebook serializer for a file.

    Args:
        path: File path

    Returns:
        Appropriate notebook serializer

    Raises:
        ValueError: If no notebook serializer supports the file format
    """
    # Ensure path is a Path object
    if not isinstance(path, Path):
        path = Path(path)

    ext = path.suffix
    handler = DEFAULT_NOTEBOOK_SERIALIZERS.get(ext)
    if handler is None:
        raise ValueError(
            f"No notebook serializer found for {path}. Supported extensions: {list(DEFAULT_NOTEBOOK_SERIALIZERS.keys())}"
        )
    return handler
