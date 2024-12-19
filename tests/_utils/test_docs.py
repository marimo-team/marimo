from marimo._utils.docs import google_docstring_to_markdown
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
    snapshot("docstring_summary.txt", md_result)

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

    Returns:
        Html: An Html object.
    """
    md_result = google_docstring_to_markdown(docstring)
    snapshot("docstring_complex.txt", md_result)


def test_google_docstring_to_markdown_oneliner():
    docstring = """One-liner docstring"""
    md_result = google_docstring_to_markdown(docstring)
    snapshot("docstring_one_liner.txt", md_result)

    for substr in [
        "# Summary",
        "One-liner docstring",
    ]:
        assert substr in md_result
