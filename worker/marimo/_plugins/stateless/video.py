# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import io
from typing import Optional, Union

from marimo._output.builder import h
from marimo._output.hypertext import Html
from marimo._output.rich_help import mddoc
from marimo._output.utils import create_style
from marimo._plugins.core.media import io_to_data_url


@mddoc
def video(
    src: Union[str, bytes, io.BytesIO, io.BufferedReader],
    controls: bool = True,
    muted: bool = False,
    autoplay: bool = False,
    loop: bool = False,
    width: Optional[int] = None,
    height: Optional[int] = None,
    rounded: bool = False,
) -> Html:
    """Render an video as HTML.

    **Example.**

    ```python3
    mo.video(
        src="https://v3.cdnpk.net/videvo_files/video/free/2013-08/large_watermarked/hd0992_preview.mp4",
        controls=False,
    )
    ```

    **Args.**

    - `src`: the URL of the video or a file-like object
    - `controls`: whether to show the controls
    - `muted`: whether to mute the video
    - `autoplay`: whether to autoplay the video.
        the video will only autoplay if `muted` is `True`
    - `loop`: whether to loop the video
    - `width`: the width of the video
    - `height`: the height of the video
    - `rounded`: whether to round the corners of the video

    **Returns.**

    `Html` object
    """
    # Convert to bytes right away since can only be read once
    if isinstance(src, io.BufferedReader):
        src.seek(0)
        src = src.read()

    resolved_src = io_to_data_url(src, fallback_mime_type="video/mp4")
    styles = create_style(
        {
            "width": f"{width}px" if width is not None else None,
            "height": f"{height}px" if height is not None else None,
            "border-radius": "4px" if rounded else None,
        }
    )
    return Html(
        h.video(
            src=resolved_src,
            controls=controls,
            style=styles,
            muted=muted,
            autoplay=autoplay,
            loop=loop,
        )
    )
