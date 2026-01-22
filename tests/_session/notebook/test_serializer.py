# Copyright 2026 Marimo. All rights reserved.
"""Tests for serializer.py"""

from __future__ import annotations

from pathlib import Path

import pytest

from marimo._schemas.serialization import (
    AppInstantiation,
    CellDef,
    Header,
    NotebookSerializationV1,
)
from marimo._session.notebook.serializer import (
    DEFAULT_NOTEBOOK_SERIALIZERS,
    MarkdownNotebookSerializer,
    PythonNotebookSerializer,
    get_notebook_serializer,
)


class TestPythonNotebookSerializer:
    def test_serialize_basic(self) -> None:
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

        result = serializer.serialize(notebook)

        assert "import marimo" in result
        assert "x = 1" in result

    def test_serialize_with_header(self) -> None:
        """Test that headers are included in output when provided in notebook."""
        serializer = PythonNotebookSerializer()

        notebook = NotebookSerializationV1(
            app=AppInstantiation(),
            header=Header(value="# Header comment\n# Another line"),
            cells=[
                CellDef(
                    name="cell1",
                    code="x = 1",
                )
            ],
        )

        result = serializer.serialize(notebook)

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

    def test_serialize_without_header(self) -> None:
        """Test serializing without a header."""
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

        result = serializer.serialize(notebook)

        # Should have import but no custom header
        assert "import marimo" in result
        assert "x = 1" in result

    def test_deserialize_basic(self) -> None:
        """Test deserializing Python notebook content."""
        serializer = PythonNotebookSerializer()
        content = """import marimo

__generated_with = "0.1.0"
app = marimo.App()

@app.cell
def __():
    x = 1
    return x,
"""

        result = serializer.deserialize(content)

        assert result is not None
        assert len(result.cells) == 1
        assert "x = 1" in result.cells[0].code
        # When no filepath is provided, defaults to "<marimo>"
        assert result.filename == "<marimo>"

    def test_deserialize_with_filepath(self) -> None:
        """Test that filepath is propagated through deserialization."""
        serializer = PythonNotebookSerializer()
        content = """import marimo

__generated_with = "0.1.0"
app = marimo.App()

@app.cell
def __():
    x = 1
    return x,
"""
        filepath = "/path/to/notebook.py"

        result = serializer.deserialize(content, filepath=filepath)

        assert result is not None
        assert result.filename == filepath
        assert len(result.cells) == 1

    def test_deserialize_empty_content(self) -> None:
        """Test deserializing empty content returns empty notebook with filepath."""
        serializer = PythonNotebookSerializer()
        filepath = "/path/to/empty.py"

        result = serializer.deserialize("", filepath=filepath)

        assert result is not None
        assert result.filename == filepath
        assert len(result.cells) == 0


class TestMarkdownNotebookSerializer:
    def test_serialize_basic(self) -> None:
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

        result = serializer.serialize(notebook)

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

    def test_deserialize_basic(self) -> None:
        """Test deserializing Markdown notebook content."""
        serializer = MarkdownNotebookSerializer()
        content = """# My Notebook

```python {.marimo}
x = 1
```
"""

        result = serializer.deserialize(content)

        assert result is not None
        assert len(result.cells) == 2  # markdown cell + code cell
        assert result.filename is None

    def test_deserialize_with_filepath(self) -> None:
        """Test that filepath is propagated through markdown deserialization."""
        serializer = MarkdownNotebookSerializer()
        content = """# My Notebook

```python {.marimo}
x = 1
```
"""
        filepath = "/path/to/notebook.md"

        result = serializer.deserialize(content, filepath=filepath)

        assert result is not None
        assert result.filename == filepath
        assert len(result.cells) == 2

    def test_deserialize_empty_content(self) -> None:
        """Test deserializing empty markdown returns empty notebook with filepath."""
        serializer = MarkdownNotebookSerializer()
        filepath = "/path/to/empty.md"

        result = serializer.deserialize("", filepath=filepath)

        assert result is not None
        assert result.filename == filepath
        assert len(result.cells) == 0

    def test_deserialize_with_frontmatter(self) -> None:
        """Test deserializing markdown with frontmatter preserves filepath and metadata."""
        serializer = MarkdownNotebookSerializer()
        content = """---
title: "Test Notebook"
---

# Content

```python {.marimo}
print("hello")
```
"""
        filepath = "/path/to/notebook.md"

        result = serializer.deserialize(content, filepath=filepath)

        assert result is not None
        assert result.filename == filepath
        assert len(result.cells) == 2
        # Frontmatter title is parsed and set in app options
        assert result.app.options.get("app_title") == "Test Notebook"


class TestGetFormatHandler:
    def test_get_python_handler(self, tmp_path: Path) -> None:
        path = tmp_path / "notebook.py"

        handler = get_notebook_serializer(path)

        assert isinstance(handler, PythonNotebookSerializer)

    def test_get_markdown_handler(self, tmp_path: Path) -> None:
        path = tmp_path / "notebook.md"

        handler = get_notebook_serializer(path)

        assert isinstance(handler, MarkdownNotebookSerializer)

    def test_get_qmd_handler(self, tmp_path: Path) -> None:
        path = tmp_path / "notebook.qmd"

        handler = get_notebook_serializer(path)

        assert isinstance(handler, MarkdownNotebookSerializer)

    def test_get_handler_with_string_path(self, tmp_path: Path) -> None:
        path_str = str(tmp_path / "notebook.py")

        handler = get_notebook_serializer(Path(path_str))

        assert isinstance(handler, PythonNotebookSerializer)

    def test_unsupported_extension(self, tmp_path: Path) -> None:
        path = tmp_path / "notebook.txt"

        with pytest.raises(ValueError) as exc_info:
            get_notebook_serializer(path)

        assert "No notebook serializer found" in str(exc_info.value)
        assert ".txt" in str(exc_info.value)

    def test_default_handlers_registered(self) -> None:
        assert ".py" in DEFAULT_NOTEBOOK_SERIALIZERS
        assert ".md" in DEFAULT_NOTEBOOK_SERIALIZERS
        assert ".qmd" in DEFAULT_NOTEBOOK_SERIALIZERS


class TestDeserializationWithFilenames:
    """Test that filenames are propagated through the deserialization chain."""

    def test_python_notebook_filepath_propagation(
        self, tmp_path: Path
    ) -> None:
        """Test Python notebook filepath propagation through get_notebook_serializer."""
        filepath = tmp_path / "test.py"
        content = """import marimo
__generated_with = "0.1.0"
app = marimo.App()

@app.cell
def __():
    x = 1
    return x,
"""
        filepath.write_text(content, encoding="utf-8")

        handler = get_notebook_serializer(filepath)
        result = handler.deserialize(content, filepath=str(filepath))

        assert result.filename == str(filepath)
        assert len(result.cells) == 1

    def test_markdown_notebook_filepath_propagation(
        self, tmp_path: Path
    ) -> None:
        """Test Markdown notebook filepath propagation through get_notebook_serializer."""
        filepath = tmp_path / "test.md"
        content = """# Test

```python {.marimo}
x = 1
```
"""
        filepath.write_text(content, encoding="utf-8")

        handler = get_notebook_serializer(filepath)
        result = handler.deserialize(content, filepath=str(filepath))

        assert result.filename == str(filepath)
        assert len(result.cells) == 2

    def test_qmd_notebook_filepath_propagation(self, tmp_path: Path) -> None:
        """Test QMD notebook filepath propagation."""
        filepath = tmp_path / "test.qmd"
        content = """# Test

```python {.marimo}
x = 1
```
"""
        filepath.write_text(content, encoding="utf-8")

        handler = get_notebook_serializer(filepath)
        result = handler.deserialize(content, filepath=str(filepath))

        assert result.filename == str(filepath)
        assert isinstance(handler, MarkdownNotebookSerializer)
