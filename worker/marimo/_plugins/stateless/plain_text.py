# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from marimo._output.builder import h
from marimo._output.hypertext import Html
from marimo._output.rich_help import mddoc
from marimo._output.utils import create_style


@mddoc
def plain_text(text: str) -> Html:
    """Text that's fixed-width, with spaces and newlines preserved.

    **Args.**

    - `text`: text to output

    **Returns.**

    An `Html` object representing the text.
    """
    styles = create_style({"font-size": "12px"})
    img = h.pre(child=text, style=styles)
    return Html(img)
