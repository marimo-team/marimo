# Copyright 2024 Marimo. All rights reserved.
from marimo._output.formatting import as_html
from marimo._output.hypertext import Html
from marimo._output.rich_help import mddoc


@mddoc
def center(item: object) -> Html:
    """Center an item.

    **Returns.**

    A centered `Html` object.
    """
    return as_html(item).center()


@mddoc
def left(item: object) -> Html:
    """Left-justify an item.

    **Returns.**

    A left-justified `Html` object.
    """
    return as_html(item).left()


@mddoc
def right(item: object) -> Html:
    """Right-justify an item.

    **Returns.**

    A right-justified `Html` object.
    """
    return as_html(item).right()
