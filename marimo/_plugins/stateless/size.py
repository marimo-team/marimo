# Copyright 2023 Marimo. All rights reserved.
from marimo._output.builder import h
from marimo._output.formatting import as_html
from marimo._output.hypertext import Html
from marimo._output.rich_help import mddoc


@mddoc
def max_height(item: object, height: float) -> Html:
    """Output an item with a max height

    **Args.**

    - `height`: height in pixels
    """
    return Html(
        h.div(
            children=as_html(item).text,
            style=f"max-height: {height}px; overflow: auto",
        )
    )


@mddoc
def max_width(item: object, width: float) -> Html:
    """Output an item with a max width

    **Args.**

    - `width`: width in pixels
    """
    return Html(
        h.div(
            children=as_html(item).text,
            style=f"max-width: {width}px; overflow: auto",
        )
    )
