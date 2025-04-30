from marimo._ast.compiler import compile_cell
from marimo._server.export.utils import get_markdown_from_cell


def test_extract_markdown_base():
    empty_markdown_str = "mo.md('hello')"
    markdown = get_markdown_from_cell(
        compile_cell(empty_markdown_str, "id"), empty_markdown_str
    )
    assert markdown == "hello"


def test_extract_markdown_empty():
    empty_markdown_str = "mo.md()"
    markdown = get_markdown_from_cell(
        compile_cell(empty_markdown_str, "id"), empty_markdown_str
    )
    assert markdown is None


def test_extract_markdown_broken():
    empty_markdown_str = "mo.md()"
    # This can occur because the cell isn't recompiled at this point.
    markdown = get_markdown_from_cell(
        compile_cell(empty_markdown_str, "id"), "mo.md(f'{broken(}')"
    )
    assert markdown is None
