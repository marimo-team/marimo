from marimo._snippets.snippets import get_title_from_code, read_snippets


async def test_snippets():
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


def test_get_title_from_code_empty():
    assert get_title_from_code("") == ""


def test_get_title_from_code_with_title():
    code = "# This is a title\nprint('Hello, world!')"
    assert get_title_from_code(code) == "This is a title"


def test_get_title_from_code_without_title():
    code = "print('Hello, world!')"
    assert get_title_from_code(code) == ""


def test_get_title_from_code_with_multiple_titles():
    code = "# First title\nprint('Hello, world!')\n# Second title"
    assert get_title_from_code(code) == "First title"


def test_get_title_from_code_with_non_title_hashes():
    code = "print('# This is not a title')"
    assert get_title_from_code(code) == ""
