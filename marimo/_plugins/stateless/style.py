# Copyright 2023 Marimo. All rights reserved.
from marimo._output.builder import h
from marimo._output.formatting import as_html
from marimo._output.hypertext import Html
from marimo._output.rich_help import mddoc


@mddoc
def style(item: object, style: str) -> Html:
    """Wrap an object in a styled container.

    **Example.**

    ```python
    mo.style(item, style="max-height: 300px; overflow: auto")
    ```

    **Args.**

    - `item`: an object to render as HTML
    - `style`: a string of inline styles for `item`'s container
    """
    return Html(h.div(children=as_html(item).text, style=style))
