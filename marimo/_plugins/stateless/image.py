# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any, Optional

from marimo._output.builder import h
from marimo._output.hypertext import Html
from marimo._output.rich_help import mddoc
from marimo._output.utils import create_style


@mddoc
def image(
    src: str,
    alt: Optional[str] = None,
    width: Optional[int] = None,
    height: Optional[int] = None,
    rounded: bool = False,
    style: Optional[dict[str, Any]] = None,
) -> Html:
    """Render an image as HTML.

    **Example.**
    ```python3
    mo.image(
        src="https://marimo.io/logo.png",
        alt="Marimo logo",
        width=100,
        height=100,
        rounded=True,
    )
    ```
    **Args.**

    - `src`: the URL of the image
    - `alt`: the alt text of the image
    - `width`: the width of the image
    - `height`: the height of the image
    - `rounded`: whether to round the corners of the image
    - `style`: a dictionary of CSS styles to apply to the image

    **Returns.**

    `Html` object
    """
    styles = create_style(
        {
            "width": width,
            "height": height,
            "border-radius": "4px" if rounded else None,
            **(style or {}),
        }
    )
    img = h.img(src=src, alt=alt, style=styles)
    return Html(img)
