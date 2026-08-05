# Copyright 2026 Marimo. All rights reserved.
"""Format handlers for different notebook file formats."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from marimo._ast.parse import is_non_marimo_python_script
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

        Returns:
            Serialized notebook content as string
        """
        ...

    def deserialize(
        self, content: str, filepath: str | None = None
    ) -> NotebookSerializationV1:
        """Convert content string to notebook IR.

        Args:
            content: File content as string
            filepath: Optional file path for error reporting

        Returns:
            Notebook in intermediate representation
        """
        ...

    def extract_header(self, path: Path) -> str | None:
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
        self, content: str, filepath: str | None = None
    ) -> NotebookSerializationV1:
        """Deserialize Python notebook content to IR."""
        from marimo._ast.parse import parse_notebook

        notebook = parse_notebook(content, filepath=filepath or "<marimo>")
        return notebook or NotebookSerializationV1(
            app=AppInstantiation(options={}), filename=filepath
        )

    def extract_header(self, path: Path) -> str | None:
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
        self, content: str, filepath: str | None = None
    ) -> NotebookSerializationV1:
        """Deserialize Markdown notebook content to IR."""
        from marimo._convert.markdown.to_ir import convert_from_md_to_marimo_ir

        return convert_from_md_to_marimo_ir(content, filepath=filepath)

    def extract_header(self, path: Path) -> str | None:
        """Extract full frontmatter metadata from Markdown file as YAML.

        Unlike Python files where only the script preamble matters, markdown
        frontmatter and MyST marimo-config directives can carry metadata that
        must survive through the save lifecycle. Return the full metadata as
        YAML so _save_file() preserves it all.
        """
        from marimo._convert.markdown.flavor.mystmd import (
            extract_mystmd_config_metadata,
        )
        from marimo._convert.markdown.to_ir import extract_frontmatter
        from marimo._utils import yaml

        markdown = path.read_text(encoding="utf-8")
        frontmatter, _ = extract_frontmatter(markdown)
        metadata = dict(frontmatter or {})
        metadata.update(extract_mystmd_config_metadata(markdown))
        if not metadata:
            return None
        return yaml.dump(metadata, sort_keys=False)


# Default format handlers
DEFAULT_NOTEBOOK_SERIALIZERS = {
    ".py": PythonNotebookSerializer(),
    ".md": MarkdownNotebookSerializer(),
    ".qmd": MarkdownNotebookSerializer(),
}


def get_notebook_serializer(
    path: Path,
    contents: str | None = None,
    default: str | None = None,
) -> NotebookSerializer:
    """Get the appropriate notebook serializer for a file.

    Args:
        path: File path
        contents: Optional file contents. A path with an unrecognized
            suffix (for example, Slurm's spooled copy of a submitted
            notebook, which has no extension) resolves to the `default`
            serializer when the contents are a marimo notebook.
        default: Suffix of the serializer to fall back to

    Returns:
        Appropriate notebook serializer

    Raises:
        ValueError: If no notebook serializer supports the file
    """
    # Ensure path is a Path object
    if not isinstance(path, Path):
        path = Path(path)

    handler = DEFAULT_NOTEBOOK_SERIALIZERS.get(path.suffix)
    if (
        handler is None
        and path.suffix == ""
        and default is not None
        and contents is not None
    ):
        fallback = DEFAULT_NOTEBOOK_SERIALIZERS.get(default)
        if fallback is not None:
            from marimo._ast.parse import MarimoFileError

            try:
                notebook = fallback.deserialize(contents, filepath=str(path))
            except SyntaxError:
                # Preserve SyntaxError semantics for extensionless Python files.
                handler = fallback
            except MarimoFileError:
                notebook = None
            else:
                if notebook is not None and not is_non_marimo_python_script(notebook):
                    handler = fallback
    if handler is None:
        raise ValueError(
            f"No notebook serializer found for {path}. Supported extensions: {list(DEFAULT_NOTEBOOK_SERIALIZERS.keys())}"
        )
    return handler
