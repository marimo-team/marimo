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
    IpynbNotebookSerializer,
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


class TestIpynbNotebookSerializer:
    def test_deserialize_basic_ipynb(self) -> None:
        """Test deserializing a basic ipynb notebook."""
        serializer = IpynbNotebookSerializer()

        # Create a simple ipynb structure
        import json

        ipynb_content = json.dumps(
            {
                "cells": [
                    {
                        "cell_type": "code",
                        "source": ["import marimo\n", "x = 1"],
                        "metadata": {},
                    }
                ],
                "metadata": {
                    "kernelspec": {
                        "display_name": "Python 3",
                        "language": "python",
                        "name": "python3",
                    },
                    "language_info": {"name": "python", "version": "3.11.0"},
                },
                "nbformat": 4,
                "nbformat_minor": 5,
            }
        )

        result = serializer.deserialize(ipynb_content)

        assert result is not None
        assert len(result.cells) >= 1
        # Should contain the code we put in
        assert any("import marimo" in cell.code for cell in result.cells)

    def test_deserialize_ipynb_with_filepath(self) -> None:
        """Test that filepath is propagated through ipynb deserialization."""
        serializer = IpynbNotebookSerializer()

        import json

        ipynb_content = json.dumps(
            {
                "cells": [
                    {"cell_type": "code", "source": ["x = 1"], "metadata": {}}
                ],
                "metadata": {},
                "nbformat": 4,
                "nbformat_minor": 5,
            }
        )

        filepath = "/path/to/notebook.ipynb"
        result = serializer.deserialize(ipynb_content, filepath=filepath)

        assert result is not None
        assert result.filename == filepath

    def test_extract_header_ipynb(self, tmp_path: Path) -> None:
        """Test extract_header for ipynb files (returns None as metadata is handled differently)."""
        serializer = IpynbNotebookSerializer()
        test_file = tmp_path / "notebook.ipynb"

        import json

        ipynb_content = json.dumps(
            {"cells": [], "metadata": {}, "nbformat": 4, "nbformat_minor": 5}
        )

        test_file.write_text(ipynb_content, encoding="utf-8")

        # extract_header should return None for ipynb as metadata is handled differently
        header = serializer.extract_header(test_file)

        assert header is None


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

    def test_get_ipynb_handler(self, tmp_path: Path) -> None:
        path = tmp_path / "notebook.ipynb"

        handler = get_notebook_serializer(path)

        assert isinstance(handler, IpynbNotebookSerializer)

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
        assert ".ipynb" in DEFAULT_NOTEBOOK_SERIALIZERS


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

    def test_ipynb_notebook_filepath_propagation(self, tmp_path: Path) -> None:
        """Test ipynb notebook filepath propagation."""
        import json

        filepath = tmp_path / "test.ipynb"
        content = json.dumps(
            {
                "cells": [
                    {"cell_type": "code", "source": ["x = 1"], "metadata": {}}
                ],
                "metadata": {},
                "nbformat": 4,
                "nbformat_minor": 5,
            }
        )
        filepath.write_text(content, encoding="utf-8")

        handler = get_notebook_serializer(filepath)
        result = handler.deserialize(content, filepath=str(filepath))

        assert result.filename == str(filepath)
        assert isinstance(handler, IpynbNotebookSerializer)


class TestIsMarimoNotebook:
    """Tests for the ``is_marimo_notebook`` detection method on each serializer."""

    # --- PythonNotebookSerializer ---

    def test_python_marimo_detected(self, tmp_path: Path) -> None:
        serializer = PythonNotebookSerializer()
        f = tmp_path / "app.py"
        f.write_text("import marimo\napp = marimo.App()\n")
        assert serializer.is_marimo_notebook(f) is True

    def test_python_non_marimo(self, tmp_path: Path) -> None:
        serializer = PythonNotebookSerializer()
        f = tmp_path / "other.py"
        f.write_text("import sys\nprint('hi')\n")
        assert serializer.is_marimo_notebook(f) is False

    def test_python_marimo_with_long_docstring(self, tmp_path: Path) -> None:
        """Long docstring must not hide markers (slow-path test)."""
        serializer = PythonNotebookSerializer()
        f = tmp_path / "app.py"
        f.write_text(
            '"""'
            + ("x" * 1024)
            + '"""\n'
            + "import marimo\napp = marimo.App()\n"
        )
        assert serializer.is_marimo_notebook(f) is True

    def test_python_non_marimo_long(self, tmp_path: Path) -> None:
        """Slow-path scan still rejects non-marimo Python files."""
        serializer = PythonNotebookSerializer()
        f = tmp_path / "other.py"
        f.write_text('"""' + ("x" * 1024) + '"""\nimport sys\nprint("hi")\n')
        assert serializer.is_marimo_notebook(f) is False

    def test_python_missing_file(self, tmp_path: Path) -> None:
        serializer = PythonNotebookSerializer()
        f = tmp_path / "nonexistent.py"
        assert serializer.is_marimo_notebook(f) is False

    # --- MarkdownNotebookSerializer ---

    def test_markdown_marimo_detected(self, tmp_path: Path) -> None:
        serializer = MarkdownNotebookSerializer()
        f = tmp_path / "notebook.md"
        f.write_text("---\nmarimo-version: 0.1.0\n---\n")
        assert serializer.is_marimo_notebook(f) is True

    def test_markdown_non_marimo(self, tmp_path: Path) -> None:
        serializer = MarkdownNotebookSerializer()
        f = tmp_path / "plain.md"
        f.write_text("# Just markdown\n")
        assert serializer.is_marimo_notebook(f) is False

    def test_markdown_marimo_long_frontmatter(self, tmp_path: Path) -> None:
        """Long YAML frontmatter must not hide marimo-version marker."""
        serializer = MarkdownNotebookSerializer()
        padding = "\n".join(f"key{i}: value{i}" for i in range(50))
        content = f"---\n{padding}\nmarimo-version: 0.1.0\n---\n"
        assert len(content.encode()) > 512  # exercise the slow path
        f = tmp_path / "notebook.md"
        f.write_text(content)
        assert serializer.is_marimo_notebook(f) is True

    def test_markdown_missing_file(self, tmp_path: Path) -> None:
        serializer = MarkdownNotebookSerializer()
        f = tmp_path / "nonexistent.md"
        assert serializer.is_marimo_notebook(f) is False

    # --- IpynbNotebookSerializer ---

    def test_ipynb_marimo_detected(self, tmp_path: Path) -> None:
        """Ipynb with marimo metadata is detected."""
        import json

        serializer = IpynbNotebookSerializer()
        f = tmp_path / "notebook.ipynb"
        data = {
            "cells": [],
            "metadata": {"marimo": {"marimo_version": "0.1.0"}},
            "nbformat": 4,
            "nbformat_minor": 5,
        }
        f.write_text(json.dumps(data))
        assert serializer.is_marimo_notebook(f) is True

    def test_ipynb_non_marimo(self, tmp_path: Path) -> None:
        """Standard Jupyter ipynb without marimo metadata is not detected."""
        import json

        serializer = IpynbNotebookSerializer()
        f = tmp_path / "plain.ipynb"
        data = {
            "cells": [],
            "metadata": {
                "kernelspec": {
                    "display_name": "Python 3",
                    "language": "python",
                    "name": "python3",
                }
            },
            "nbformat": 4,
            "nbformat_minor": 5,
        }
        f.write_text(json.dumps(data))
        assert serializer.is_marimo_notebook(f) is False

    def test_ipynb_empty_metadata(self, tmp_path: Path) -> None:
        """Ipynb with empty metadata dict is not a marimo notebook."""
        import json

        serializer = IpynbNotebookSerializer()
        f = tmp_path / "empty.ipynb"
        data = {
            "cells": [],
            "metadata": {},
            "nbformat": 4,
            "nbformat_minor": 5,
        }
        f.write_text(json.dumps(data))
        assert serializer.is_marimo_notebook(f) is False

    def test_ipynb_invalid_json(self, tmp_path: Path) -> None:
        """Invalid JSON is handled gracefully."""
        serializer = IpynbNotebookSerializer()
        f = tmp_path / "bad.ipynb"
        f.write_text("not valid json")
        assert serializer.is_marimo_notebook(f) is False

    def test_ipynb_missing_file(self, tmp_path: Path) -> None:
        serializer = IpynbNotebookSerializer()
        f = tmp_path / "nonexistent.ipynb"
        assert serializer.is_marimo_notebook(f) is False


def _check_round_trip(
    serializer: PythonNotebookSerializer
    | MarkdownNotebookSerializer
    | IpynbNotebookSerializer,
    original: NotebookSerializationV1,
    *,
    expected_cells: int,
    expected_fragments: list[str],
    expected_header: str | None = None,
) -> None:
    """Serialize *original*, deserialize the result, and verify fidelity."""
    serialized = serializer.serialize(original)
    deserialized = serializer.deserialize(serialized)

    assert deserialized is not None
    assert len(deserialized.cells) == expected_cells
    for fragment in expected_fragments:
        assert any(fragment in cell.code for cell in deserialized.cells), (
            f"Expected fragment {fragment!r} not found in any cell"
        )
    if expected_header is not None:
        assert deserialized.header is not None
        assert expected_header in deserialized.header.value


_PYTHON_BASIC = NotebookSerializationV1(
    app=AppInstantiation(),
    cells=[
        CellDef(name="cell1", code="x = 1"),
        CellDef(name="cell2", code="y = x + 1"),
    ],
)
_PYTHON_WITH_HEADER = NotebookSerializationV1(
    app=AppInstantiation(),
    header=Header(value="# Test header\n# More info"),
    cells=[CellDef(name="cell1", code="x = 1")],
)
_MARKDOWN = NotebookSerializationV1(
    app=AppInstantiation(),
    cells=[
        CellDef(name="md_cell", code="# Title"),
        CellDef(name="code_cell", code="x = 1"),
    ],
)
_IPYNB = NotebookSerializationV1(
    app=AppInstantiation(),
    cells=[
        CellDef(name="cell1", code="import marimo"),
        CellDef(name="cell2", code="x = 42"),
    ],
)


class TestRoundTripSerialization:
    """Parameterized round-trip (serialize → deserialize) for all format handlers."""

    @pytest.mark.parametrize(
        "serializer, original, expected_cells, fragments, header",
        [
            pytest.param(
                PythonNotebookSerializer(),
                _PYTHON_BASIC,
                2,
                ["x = 1", "y = x + 1"],
                None,
                id="python_basic",
            ),
            pytest.param(
                PythonNotebookSerializer(),
                _PYTHON_WITH_HEADER,
                1,
                ["x = 1"],
                "# Test header",
                id="python_with_header",
            ),
            pytest.param(
                MarkdownNotebookSerializer(),
                _MARKDOWN,
                2,
                ["# Title", "x = 1"],
                None,
                id="markdown",
            ),
            pytest.param(
                IpynbNotebookSerializer(),
                _IPYNB,
                2,
                ["x = 42"],
                None,
                id="ipynb",
            ),
        ],
    )
    def test_format_round_trip(
        self,
        serializer: PythonNotebookSerializer
        | MarkdownNotebookSerializer
        | IpynbNotebookSerializer,
        original: NotebookSerializationV1,
        expected_cells: int,
        fragments: list[str],
        header: str | None,
    ) -> None:
        _check_round_trip(
            serializer,
            original,
            expected_cells=expected_cells,
            expected_fragments=fragments,
            expected_header=header,
        )
