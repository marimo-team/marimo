# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import io
import os
from typing import Any, Optional, Union

import marimo._output.data.data as mo_data
from marimo._output.builder import h
from marimo._output.hypertext import Html
from marimo._output.rich_help import mddoc
from marimo._output.utils import create_style
from marimo._plugins.core.media import io_to_data_url


@mddoc
def image(
    src: Union[str, bytes, io.BytesIO, io.BufferedReader],
    alt: Optional[str] = None,
    width: Optional[int] = None,
    height: Optional[int] = None,
    rounded: bool = False,
    style: Optional[dict[str, Any]] = None,
) -> Html:
    """Render an image as HTML.

    **Examples.**

    ```python3
    # Render an image from a local file
    mo.image(src="path/to/image.png")
    ```

    ```python3
    # Render an image from a URL
    mo.image(
        src="https://marimo.io/logo.png",
        alt="Marimo logo",
        width=100,
        height=100,
        rounded=True,
    )
    ```

    **Args.**

    - `src`: a path or URL to an image, or a file-like object
        (opened in binary mode)
    - `alt`: the alt text of the image
    - `width`: the width of the image in pixels
    - `height`: the height of the image in pixels
    - `rounded`: whether to round the corners of the image
    - `style`: a dictionary of CSS styles to apply to the image

    **Returns.**

    `Html` object
    """
    # Convert to virtual file
    resolved_src: Optional[str]
    if isinstance(src, io.BufferedReader) or isinstance(src, io.BytesIO):
        src.seek(0)
        resolved_src = mo_data.image(src.read()).url
    elif isinstance(src, bytes):
        resolved_src = mo_data.image(src).url
    elif isinstance(src, str) and os.path.isfile(src):
        with open(src, "rb") as f:
            resolved_src = mo_data.image(
                f.read(), ext=os.path.splitext(src)[1]
            ).url
    else:
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
