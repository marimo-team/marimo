# Copyright 2026 Marimo. All rights reserved.
"""Format handlers for different notebook file formats."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

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

    def is_marimo_notebook(self, path: Path) -> bool:
        """Check if a file is a marimo notebook.

        Args:
            path: File path to check

        Returns:
            True if the file is a marimo notebook, False otherwise
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

    def is_marimo_notebook(self, path: Path) -> bool:
        """Check if a Python file is a marimo notebook.

        Scans the file for ``import marimo`` and ``marimo.App`` markers.
        First reads 512 bytes (fast path), and on a miss reads up to 1 MB.
        """
        FAST_PATH_BYTES = 512
        MAX_SCAN_BYTES = 1 * 1024 * 1024  # 1 MB

        markers: tuple[bytes, ...] = (b"import marimo", b"marimo.App")

        def matches(content: bytes) -> bool:
            return all(m in content for m in markers)

        try:
            with open(path, "rb") as f:
                header = f.read(FAST_PATH_BYTES)
                if matches(header):
                    return True
                if len(header) < FAST_PATH_BYTES:
                    return False
                rest = f.read(MAX_SCAN_BYTES - FAST_PATH_BYTES)
                return matches(header + rest)
        except Exception:
            return False


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

    def is_marimo_notebook(self, path: Path) -> bool:
        """Check if a Markdown file is a marimo notebook.

        Scans the file for the ``marimo-version:`` frontmatter marker.
        First reads 512 bytes (fast path), and on a miss reads up to 1 MB.
        """
        FAST_PATH_BYTES = 512
        MAX_SCAN_BYTES = 1 * 1024 * 1024  # 1 MB

        marker: bytes = b"marimo-version:"

        try:
            with open(path, "rb") as f:
                header = f.read(FAST_PATH_BYTES)
                if marker in header:
                    return True
                if len(header) < FAST_PATH_BYTES:
                    return False
                rest = f.read(MAX_SCAN_BYTES - FAST_PATH_BYTES)
                return marker in (header + rest)
        except Exception:
            return False


class IpynbNotebookSerializer(NotebookSerializer):
    """Handler for Jupyter Notebook (.ipynb) files."""

    def serialize(self, notebook: NotebookSerializationV1) -> str:
        """Serialize notebook to Jupyter ipynb format."""
        from marimo._convert.ipynb.from_ir import ir_to_ipynb

        return ir_to_ipynb(notebook, session_view=None)

    def deserialize(
        self, content: str, filepath: str | None = None
    ) -> NotebookSerializationV1:
        """Deserialize Jupyter ipynb notebook content to IR."""
        from marimo._convert.ipynb.to_ir import (
            convert_from_ipynb_to_notebook_ir,
        )

        return convert_from_ipynb_to_notebook_ir(content, filepath=filepath)

    def extract_header(self, path: Path) -> str | None:
        """Extract header/metadata from ipynb file.

        For now, returns None as ipynb metadata is handled differently.
        The metadata is preserved through the serialize/deserialize cycle.
        """
        return None

    def is_marimo_notebook(self, path: Path) -> bool:
        """Check if an ipynb file is a marimo notebook.

        Checks for the presence of ``metadata.marimo`` key in the notebook
        JSON structure — marimo-generated ipynb files include this metadata.
        """
        import json

        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            metadata = data.get("metadata", {})
            return "marimo" in metadata
        except Exception:
            return False


# Default format handlers
DEFAULT_NOTEBOOK_SERIALIZERS = {
    ".py": PythonNotebookSerializer(),
    ".md": MarkdownNotebookSerializer(),
    ".qmd": MarkdownNotebookSerializer(),
    ".ipynb": IpynbNotebookSerializer(),
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
