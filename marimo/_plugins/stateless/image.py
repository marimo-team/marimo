# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

import io
from typing import Any, Optional, Union

from marimo._output.builder import h
from marimo._output.hypertext import Html
from marimo._output.rich_help import mddoc
from marimo._output.utils import create_style
from marimo._plugins.core.media import io_to_data_url


@mddoc
def image(
    src: Union[str, io.BytesIO],
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

    with open("logo.png", "rb") as file:
        mo.image(src=file)
    ```

    **Args.**

    - `src`: the URL of the image or a file-like object
    - `alt`: the alt text of the image
    - `width`: the width of the image in pixels
    - `height`: the height of the image in pixels
    - `rounded`: whether to round the corners of the image
    - `style`: a dictionary of CSS styles to apply to the image

    **Returns.**

    `Html` object
    """
    resolved_src = io_to_data_url(src, fallback_mime_type="image/png")
    styles = create_style(
        {
            "width": f"{width}px" if width is not None else None,
            "height": f"{height}px" if height is not None else None,
            "border-radius": "4px" if rounded else None,
            **(style or {}),
        }
    )
    img = h.img(src=resolved_src, alt=alt, style=styles)
    return Html(img)
