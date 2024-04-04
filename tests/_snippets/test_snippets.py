from marimo._snippets.snippets import read_snippets


def test_snippets():
    snippets = read_snippets()
    assert len(snippets.snippets) > 0
    # All have titles
    assert all(s.title for s in snippets.snippets)
    # All have more than one section
    assert all(len(s.sections) > 1 for s in snippets.snippets)
    # All have a code section
    assert all(
        any(section.code for section in s.sections) for s in snippets.snippets
    )
