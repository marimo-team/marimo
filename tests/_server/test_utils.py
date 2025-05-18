# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from marimo._server.api.utils import parse_title


# The function to be tested
def test_parse_title() -> None:
    assert parse_title(None) == "marimo"
    assert parse_title("example_file.txt") == "example file"
    assert (
        parse_title("another_example_file_with_underscores.docx")
        == "another example file with underscores"
    )
    assert (
        parse_title("/path/to/some_kind_of_document.pdf")
        == "some kind of document"
    )
    assert parse_title("no_extension") == "no extension"
    assert parse_title("") == ""
    assert (
        parse_title("file_with_multiple..dots.ext")
        == "file with multiple..dots"
    )
