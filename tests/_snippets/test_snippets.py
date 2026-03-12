from __future__ import annotations

from pathlib import Path

import pytest

from marimo._config.config import merge_default_config
from marimo._snippets.snippets import (
    get_title_from_code,
    read_snippet_filenames,
    read_snippets,
)
from marimo._utils.platform import is_windows

TEST_DATA_DIR = str(Path(__file__).parent / "data")


async def test_snippets() -> None:
    snippets = await read_snippets(merge_default_config({}))
    assert len(snippets.snippets) > 0
    # All have titles
    for s in snippets.snippets:
        assert s.title
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


def test_get_title_from_code_with_mo_md() -> None:
    code = "mo.md('# This is a title')"
    assert get_title_from_code(code) == "This is a title"
    code = 'mo.md("# This is a title")'
    assert get_title_from_code(code) == "This is a title"
    code = 'mo.md(r"""# This is a title""")'
    assert get_title_from_code(code) == "This is a title"


async def test_snippets_with_multiple_markdown_cells() -> None:
    """Regression test: all markdown cells should be rendered, not just the title."""
    config = merge_default_config(
        {
            "snippets": {
                "include_default_snippets": False,
                "custom_paths": [TEST_DATA_DIR],
            }
        }
    )
    snippets = await read_snippets(config)
    assert len(snippets.snippets) == 1
    snippet = snippets.snippets[0]
    assert snippet.title == "Multi Markdown Snippet"

    html_sections = [s for s in snippet.sections if s.html is not None]
    code_sections = [s for s in snippet.sections if s.code is not None]

    # Both markdown cells should be rendered as HTML sections
    assert len(html_sections) == 2, (
        f"Expected 2 HTML sections (title + description), got {len(html_sections)}"
    )
    # The code cell should be rendered
    assert len(code_sections) == 1


total_snippets = len(list(read_snippet_filenames(True, [])))


@pytest.mark.xfail(condition=is_windows(), reason="flaky on Windows")
@pytest.mark.parametrize(
    ("include_default_snippets", "custom_paths", "expected_snippets"),
    [
        (True, [], total_snippets),
        (False, [], 0),
        (True, ["/notarealdirectory"], total_snippets),
        (False, ["/notarealdirectory"], 0),
        (False, ["marimo/_snippets/data"], total_snippets),
        (
            False,
            ["marimo/_snippets/data", "/notarealdirectory"],
            total_snippets,
        ),
    ],
)
def test_read_snippet_filenames(
    include_default_snippets: bool,
    custom_paths: list[str],
    expected_snippets: int,
) -> None:
    filenames = list(
        read_snippet_filenames(include_default_snippets, custom_paths)
    )
    assert total_snippets > 0
    assert len(filenames) == expected_snippets
    assert all(filename.endswith(".py") for filename in filenames)
    assert all("_snippets/data" in filename for filename in filenames)
