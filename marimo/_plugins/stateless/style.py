# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any

from marimo._output.builder import h
from marimo._output.formatting import as_html
from marimo._output.hypertext import Html
from marimo._output.rich_help import mddoc


@mddoc
def style(item: object, styles: dict[str, Any]) -> Html:
    """Wrap an object in a styled container.

    **Example.**

    ```python
    mo.style(item, styles={"max-height": "300px", "overflow": "auto"})
    ```

    **Args.**

    - `item`: an object to render as HTML
    - `styles`: a dict of CSS styles, keyed by property name
    """
    style_str = ";".join([f"{key}:{value}" for key, value in styles.items()])
    return Html(h.div(children=as_html(item).text, style=style_str))
