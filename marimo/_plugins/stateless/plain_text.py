# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import html

from marimo._output.builder import h
from marimo._output.hypertext import Html
from marimo._output.rich_help import mddoc


@mddoc
def plain_text(text: str) -> Html:
    """Text that's fixed-width, with spaces and newlines preserved.

    Args:
        text: text to output

    Returns:
        An `Html` object representing the text.
    """
    img = h.pre(child=html.escape(text), class_="text-xs")
    return Html(img)
