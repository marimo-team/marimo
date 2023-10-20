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
def video(
    src: Union[str, bytes, io.BytesIO, io.BufferedReader],
    controls: bool = True,
    width: Optional[int] = None,
    height: Optional[int] = None,
    rounded: bool = False,
    style: Optional[dict[str, Any]] = None,
) -> Html:
    """Render an video as HTML.

    **Example.**

    ```python3
    mo.video(
        src="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        controls=False,
    )
    ```

    **Args.**

    - `src`: the URL of the video or a file-like object
    - `controls`: whether to show the controls

    **Returns.**

    `Html` object
    """
    # Convert to bytes right away since can only be read once
    if isinstance(src, io.BufferedReader):
        src.seek(0)
        src = src.read()

    resolved_src = io_to_data_url(src, fallback_mime_type="video/png")
    styles = create_style(
        {
            "width": f"{width}px" if width is not None else None,
            "height": f"{height}px" if height is not None else None,
            "border-radius": "4px" if rounded else None,
            **(style or {}),
        }
    )
    return Html(h.video(src=resolved_src, controls=controls, style=styles))
