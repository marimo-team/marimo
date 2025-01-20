from __future__ import annotations

import pytest

from marimo._snippets.snippets import (
    get_title_from_code,
    read_snippet_filenames,
    read_snippets,
)
from marimo._utils.platform import is_windows


async def test_snippets() -> None:
    snippets = await read_snippets()
    assert len(snippets.snippets) > 0
    # All have titles
    assert all(s.title for s in snippets.snippets)
    # All have more than one section
    assert all(len(s.sections) > 1 for s in snippets.snippets)
    # All have a code section
    assert all(
        any(section.code for section in s.sections) for s in snippets.snippets
    )


def test_get_title_from_code_empty() -> None:
    assert get_title_from_code("") == ""


def test_get_title_from_code_with_title() -> None:
    code = "# This is a title\nprint('Hello, world!')"
    assert get_title_from_code(code) == "This is a title"


def test_get_title_from_code_without_title() -> None:
    code = "print('Hello, world!')"
    assert get_title_from_code(code) == ""


def test_get_title_from_code_with_multiple_titles() -> None:
    code = "# First title\nprint('Hello, world!')\n# Second title"
    assert get_title_from_code(code) == "First title"


def test_get_title_from_code_with_non_title_hashes() -> None:
    code = "print('# This is not a title')"
    assert get_title_from_code(code) == ""


@pytest.mark.xfail(condition=is_windows(), reason="flaky on Windows")
@pytest.mark.parametrize(
    ("include_default_snippets", "custom_paths", "expected_snippets"),
    [
        (True, [], 38),
        (False, [], 0),
        (True, ["/notarealdirectory"], 38),
        (False, ["/notarealdirectory"], 0),
        (False, ["marimo/_snippets/data"], 38),
        (False, ["marimo/_snippets/data", "/notarealdirectory"], 38),
    ],
)
def test_read_snippet_filenames(
    include_default_snippets, custom_paths, expected_snippets
) -> None:
    filenames = list(
        read_snippet_filenames(include_default_snippets, custom_paths)
    )
    assert len(filenames) == expected_snippets
    assert all(filename.endswith(".py") for filename in filenames)
    assert all("_snippets/data" in filename for filename in filenames)
