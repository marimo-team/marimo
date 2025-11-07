# Copyright 2024 Marimo. All rights reserved.
"""Tests for serializer.py"""

from pathlib import Path

import pytest

from marimo._schemas.serialization import (
    AppInstantiation,
    CellDef,
    NotebookSerializationV1,
)
from marimo._server.notebook.serializer import (
    DEFAULT_FORMAT_HANDLERS,
    MarkdownNotebookSerializer,
    PythonNotebookSerializer,
    get_format_handler,
)


class TestPythonNotebookSerializer:
    def test_serialize_basic(self, tmp_path: Path) -> None:
        serializer = PythonNotebookSerializer()
        notebook = NotebookSerializationV1(
            app=AppInstantiation(),
            cells=[
                CellDef(
                    name="cell1",
                    code="x = 1",
                )
            ],
        )
        path = tmp_path / "notebook.py"

        result = serializer.serialize(notebook, path)

        assert "import marimo" in result
        assert "x = 1" in result

    def test_serialize_with_existing_header(self, tmp_path: Path) -> None:
        """Test that headers are preserved from existing file."""
        serializer = PythonNotebookSerializer()

        # Create existing file with header
        path = tmp_path / "notebook.py"
        path.write_text(
            "# Header comment\n# Another line\nimport marimo\n",
            encoding="utf-8",
        )

        notebook = NotebookSerializationV1(
            app=AppInstantiation(),
            cells=[
                CellDef(
                    name="cell1",
                    code="x = 1",
                )
            ],
        )

        result = serializer.serialize(notebook, path)

        assert "# Header comment" in result
        assert "import marimo" in result

    def test_extract_header_with_comments(self, tmp_path: Path) -> None:
        serializer = PythonNotebookSerializer()
        test_file = tmp_path / "notebook.py"
        test_file.write_text(
            "# Header comment\n# Another line\nimport marimo\n",
            encoding="utf-8",
        )

        header = serializer.extract_header(test_file)

        assert header is not None
        assert "Header comment" in header

    def test_extract_header_no_comments(self, tmp_path: Path) -> None:
        serializer = PythonNotebookSerializer()
        test_file = tmp_path / "notebook.py"
        test_file.write_text("import marimo\n", encoding="utf-8")

        header = serializer.extract_header(test_file)

        # No header comments should return None or empty
        assert header is None or header == ""

    def test_serialize_format_conversion(self, tmp_path: Path) -> None:
        """Test serializing when converting from one format to another."""
        serializer = PythonNotebookSerializer()

        # Create a markdown file with header
        md_file = tmp_path / "notebook.md"
        md_file.write_text(
            "---\nmarimo-version: 0.1.0\n---\n# Content\n",
            encoding="utf-8",
        )

        notebook = NotebookSerializationV1(
            app=AppInstantiation(),
            cells=[
                CellDef(
                    name="cell1",
                    code="x = 1",
                )
            ],
        )

        py_file = tmp_path / "notebook.py"
        result = serializer.serialize(notebook, py_file, previous_path=md_file)

        # Should extract header from markdown file
        assert "import marimo" in result


class TestMarkdownNotebookSerializer:
    def test_serialize_basic(self, tmp_path: Path) -> None:
        serializer = MarkdownNotebookSerializer()
        notebook = NotebookSerializationV1(
            app=AppInstantiation(),
            cells=[
                CellDef(
                    name="cell1",
                    code="print('hello')",
                )
            ],
        )
        path = tmp_path / "notebook.md"

        result = serializer.serialize(notebook, path)

        assert "```python" in result
        assert "print('hello')" in result

    def test_extract_header_with_frontmatter(self, tmp_path: Path) -> None:
        serializer = MarkdownNotebookSerializer()
        test_file = tmp_path / "notebook.md"
        markdown_content = """---
marimo-version: 0.1.0
header: |
  # Custom header
---

# Title
"""
        test_file.write_text(markdown_content, encoding="utf-8")

        header = serializer.extract_header(test_file)

        assert header is not None
        assert "Custom header" in header

    def test_extract_header_no_frontmatter(self, tmp_path: Path) -> None:
        serializer = MarkdownNotebookSerializer()
        test_file = tmp_path / "notebook.md"
        test_file.write_text("# Just markdown\n", encoding="utf-8")

        header = serializer.extract_header(test_file)

        assert header is None or header == ""


class TestGetFormatHandler:
    def test_get_python_handler(self, tmp_path: Path) -> None:
        path = tmp_path / "notebook.py"

        handler = get_format_handler(path)

        assert isinstance(handler, PythonNotebookSerializer)

    def test_get_markdown_handler(self, tmp_path: Path) -> None:
        path = tmp_path / "notebook.md"

        handler = get_format_handler(path)

        assert isinstance(handler, MarkdownNotebookSerializer)

    def test_get_qmd_handler(self, tmp_path: Path) -> None:
        path = tmp_path / "notebook.qmd"

        handler = get_format_handler(path)

        assert isinstance(handler, MarkdownNotebookSerializer)

    def test_get_handler_with_string_path(self, tmp_path: Path) -> None:
        path_str = str(tmp_path / "notebook.py")

        handler = get_format_handler(Path(path_str))

        assert isinstance(handler, PythonNotebookSerializer)

    def test_unsupported_extension(self, tmp_path: Path) -> None:
        path = tmp_path / "notebook.txt"

        with pytest.raises(ValueError) as exc_info:
            get_format_handler(path)

        assert "No format handler found" in str(exc_info.value)
        assert ".txt" in str(exc_info.value)

    def test_default_handlers_registered(self) -> None:
        assert ".py" in DEFAULT_FORMAT_HANDLERS
        assert ".md" in DEFAULT_FORMAT_HANDLERS
        assert ".qmd" in DEFAULT_FORMAT_HANDLERS
        assert len(DEFAULT_FORMAT_HANDLERS) == 3
