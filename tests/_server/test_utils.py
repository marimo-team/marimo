# Copyright 2024 Marimo. All rights reserved.
import pytest

from marimo._server.api.utils import parse_title, require_header


def test_require_header() -> None:
    # Happy path
    header = ["Content-Type"]
    assert (
        require_header(header) == "Content-Type"
    ), "The function should return the single header value"

    with pytest.raises(ValueError) as e:
        require_header(None)
    assert str(e.value) == "Expected exactly one value in header, got None"

    # Test case 3: ValueError is raised when an empty list is passed as the
    # header
    with pytest.raises(ValueError) as e:
        require_header([])
    assert (
        str(e.value)
        == "Expected exactly one value in header, got 0 values: []"
    )


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
