from marimo._utils.docs import (
    _process_code_block_content,
    google_docstring_to_markdown,
)
from tests.mocks import snapshotter

snapshot = snapshotter(__file__)


def test_google_docstring_to_markdown_summary():
    docstring = """This is the summary.

    Args:
        foo (str): Lorem ipsum
        bar (int): Dolor sit amet

    Attributes:
        baz (str): Lorem ipsum
        boo (int): Dolor sit amet

    Returns:
        bool: Return description

    Raises:
        ValueError: Something about the value

    Examples:
        ```python
        print('Hello, world!')
        print(foo, bar)
        ```
    """
    md_result = google_docstring_to_markdown(docstring)
    snapshot("docstring_summary.md", md_result)

    for substr in [
        "# Summary",
        "This is the summary.",
        "# Arguments",
        "`foo`",
        "`bar`",
        "# Attributes",
        "`baz`",
        "`boo`",
        "# Returns",
        "`bool`",
        "# Raises",
        "ValueError",
        "# Examples",
        "```python",
        "print('Hello, world!')",
    ]:
        assert substr in md_result


def test_google_docstring_to_markdown_complex():
    docstring = """
    Stack items vertically, in a column.
    Combine with `hstack` to build a grid of items.

    Examples:
        Build a column of items:
        ```python
        # Build a column of items
        mo.vstack([mo.md("..."), mo.ui.text_area()])
        ```
        Build a grid:
        ```python
        # Build a grid.
        mo.vstack(
            [
                mo.hstack([mo.md("..."), mo.ui.text_area()]),
                mo.hstack([mo.ui.checkbox(), mo.ui.text(), mo.ui.date()]),
            ]
        )
        ```

    Args:
        items (Sequence[object]): A list of items.
        align (Literal["start", "end", "center", "stretch"], optional): Align items horizontally: start, end, center, or stretch.
        justify (Literal["start", "center", "end", "space-between", "space-around"]):
            Justify items vertically: start, center, end, space-between, or space-around.
            Defaults to "start".
        gap (float, optional): Gap between items as a float in rem. 1rem is 16px by default.
            Defaults to 0.5.
        heights (Union[Literal["equal"], Sequence[float]], optional): "equal" to give items
            equal height; or a list of relative heights with same length as `items`,
            eg, [1, 2] means the second item is twice as tall as the first;
            or None for a sensible default.
        custom_css (dict[str, str], optional): Custom CSS styles for each column. Keys include:
            - width
            - height
            - background_color
            - border
            - border_radius
            - padding
        typeless: Pass unknown types to the stack.
        *args: positional arguments passed to stack
        code_block (str): Render a code block in the stack.
            ```
            mo.vstack(),
            mo.hstack()
            ```
        second_code_block (str): Render a second code block in the stack.
            ```python
            mo.vstack([])
            ```
        **kwargs: keyword arguments passed to stack

    Returns:
        Html: An Html object.
    """
    md_result = google_docstring_to_markdown(docstring)

    assert "<pre><code>mo.vstack(),<br>mo.hstack()</code></pre>" in md_result
    assert "<pre><code>mo.vstack([])</code></pre>" in md_result

    snapshot("docstring_complex.md", md_result)


def test_google_docstring_to_markdown_oneliner():
    docstring = """One-liner docstring"""
    md_result = google_docstring_to_markdown(docstring)
    snapshot("docstring_one_liner.md", md_result)

    for substr in [
        "# Summary",
        "One-liner docstring",
    ]:
        assert substr in md_result


def test_process_code_block_content():
    """Test the _process_code_block_content function with various inputs."""

    # Test with no code blocks
    result = _process_code_block_content("Simple description")
    assert result == "Simple description"

    # Test with a simple code block
    result = _process_code_block_content(
        "Description with ```python\ncode here\n```"
    )
    assert result == "Description with <pre><code>code here</code></pre>"

    # Test with code block without language
    result = _process_code_block_content(
        "Description with ```\ncode here\n```"
    )
    assert result == "Description with <pre><code>code here</code></pre>"

    # Test with multiple code blocks
    result = _process_code_block_content(
        "First ```python\ncode1\n``` Second ```\ncode2\n```"
    )
    assert (
        result
        == "First <pre><code>code1</code></pre> Second <pre><code>code2</code></pre>"
    )

    # Test with text after code block
    result = _process_code_block_content(
        "Description ```python\ncode\n``` and more text"
    )
    assert result == "Description <pre><code>code</code></pre> and more text"

    # Test with language identifier
    result = _process_code_block_content(
        "Description ```python\ncode here\n```"
    )
    assert result == "Description <pre><code>code here</code></pre>"

    # Test with empty code block
    result = _process_code_block_content("Description ```\n\n```")
    assert result == "Description <pre><code></code></pre>"
