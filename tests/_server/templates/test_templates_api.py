# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import unittest

from marimo._schemas.session import (
    VERSION,
    Cell,
    DataOutput,
    NotebookSessionMetadata,
    NotebookSessionV1,
)
from marimo._server.templates.api import (
    render_notebook,
    render_static_notebook,
)


class TestRenderNotebook(unittest.TestCase):
    def setUp(self) -> None:
        self.code = """
import marimo as mo

app = mo.App()

@app.cell
def __():
    import marimo as mo
    return mo,

@app.cell
def __(mo):
    mo.md("Hello, World!")
    return

if __name__ == "__main__":
    app.run()
"""

    def test_render_notebook_edit_mode(self) -> None:
        html = render_notebook(code=self.code, mode="edit")
        assert "<html" in html
        assert "</html>" in html

    def test_render_notebook_read_mode(self) -> None:
        html = render_notebook(code=self.code, mode="read")
        assert "<html" in html

    def test_render_notebook_with_filename(self) -> None:
        html = render_notebook(
            code=self.code, mode="edit", filename="test_notebook.py"
        )
        assert "test_notebook.py" in html

    def test_render_notebook_with_config(self) -> None:
        html = render_notebook(
            code=self.code,
            mode="edit",
            config={"completion": {"activate_on_typing": False}},
        )
        assert "activate_on_typing" in html

    def test_render_notebook_with_runtime_config(self) -> None:
        html = render_notebook(
            code=self.code,
            mode="edit",
            runtime_config=[{"url": "wss://example.com"}],
        )
        assert "wss://example.com" in html

    def test_render_notebook_with_custom_css(self) -> None:
        custom_css = "body { background-color: red; }"
        html = render_notebook(
            code=self.code, mode="edit", custom_css=custom_css
        )
        assert custom_css in html


class TestRenderStaticNotebook(unittest.TestCase):
    def setUp(self) -> None:
        self.code = """
import marimo as mo

app = mo.App()

@app.cell
def __():
    import marimo as mo
    return mo,

@app.cell
def __(mo):
    mo.md("Hello, World!")
    return

if __name__ == "__main__":
    app.run()
"""
        self.session_snapshot = NotebookSessionV1(
            version=VERSION,
            metadata=NotebookSessionMetadata(marimo_version="0.1.0"),
            cells=[
                Cell(
                    id="cell1",
                    code_hash="abc123",
                    outputs=[
                        DataOutput(
                            type="data",
                            data={"text/plain": "Hello, World!"},
                        )
                    ],
                    console=[],
                ),
            ],
        )

    def test_render_static_notebook(self) -> None:
        html = render_static_notebook(
            code=self.code, session_snapshot=self.session_snapshot
        )
        assert "<html" in html

    def test_render_static_notebook_with_filename(self) -> None:
        html = render_static_notebook(
            code=self.code,
            filename="test_notebook.py",
            session_snapshot=self.session_snapshot,
        )
        assert "test_notebook.py" in html

    def test_render_static_notebook_include_code(self) -> None:
        html_with_code = render_static_notebook(
            code=self.code,
            include_code=True,
            session_snapshot=self.session_snapshot,
        )
        html_without_code = render_static_notebook(
            code=self.code,
            include_code=False,
            session_snapshot=self.session_snapshot,
        )
        assert "import marimo as mo" in html_with_code
        assert '<marimo-code hidden=""></marimo-code>' in html_without_code
