# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import io
import os
from typing import Literal

import marimo._output.data.data as mo_data
from marimo._output.builder import h
from marimo._output.hypertext import Html
from marimo._output.rich_help import mddoc
from marimo._output.utils import create_style, normalize_dimension
from marimo._plugins.core.media import io_to_data_url
from marimo._plugins.core.web_component import (
    JSONType,
    build_stateless_plugin,
)


def _get_resolved_src(
    src: str | bytes | io.BytesIO | io.BufferedReader,
) -> str | None:
    """Determine the correct URL for the given video source.

    Local files, bytes, and file-like objects are stored as virtual files so
    that the (potentially large) video data is served via a URL rather than
    inlined as a base64 data URL. This mirrors how `mo.audio` and `mo.image`
    handle their sources.
    """
    if isinstance(src, (io.BufferedReader, io.BytesIO)):
        pos = src.tell()
        src.seek(0)
        resolved_src = mo_data.video(src.read()).url
        src.seek(pos)
        return resolved_src

    if isinstance(src, bytes):
        return mo_data.video(src).url

    if isinstance(src, str):
        expanded = os.path.expanduser(src)
        if os.path.isfile(expanded):
            with open(expanded, "rb") as f:
                ext = os.path.splitext(expanded)[1] or ".mp4"
                return mo_data.video(f.read(), ext=ext).url

    return io_to_data_url(src, fallback_mime_type="video/mp4")


@mddoc
def video(
    src: str | bytes | io.BytesIO | io.BufferedReader,
    controls: bool = True,
    muted: bool = False,
    autoplay: bool = False,
    loop: bool = False,
    width: int | str | None = None,
    height: int | str | None = None,
    rounded: bool = False,
    floating: bool | Literal["auto"] = False,
) -> Html:
    """Render a video as HTML.

    Example:
        ```python3
        # Render a video from a URL
        mo.video(
            src="https://v3.cdnpk.net/videvo_files/video/free/2013-08/large_watermarked/hd0992_preview.mp4",
            controls=False,
        )

        # Render a video from a local file
        mo.video(src="path/to/video.mp4")

        # Let the video follow the reader as they scroll
        mo.video(src="path/to/video.mp4", floating="auto")
        ```

    Args:
        src: the URL of the video, a path to a local file, `bytes`, or a
            file-like object opened in binary mode
        controls: whether to show the controls
        muted: whether to mute the video
        autoplay: whether to autoplay the video.
            the video will only autoplay if `muted` is `True`
        loop: whether to loop the video
        width: the width of the video in pixels or a string with units
        height: the height of the video in pixels or a string with units
        rounded: whether to round the corners of the video
        floating: whether the video can float above the notebook. `True` adds
            a button for moving the video between its inline and floating
            positions. `"auto"` also floats the video after it has been visible
            and is then scrolled out of view. Floating uses an in-page panel,
            not the browser's Picture-in-Picture API.

    Returns:
        `Html` object
    """
    resolved_src = _get_resolved_src(src)
    if floating is False:
        styles = create_style(
            {
                "width": normalize_dimension(width),
                "height": normalize_dimension(height),
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

    if floating is True:
        floating_mode = "manual"
    elif floating == "auto":
        floating_mode = "auto"
    else:
        raise ValueError(
            "floating must be False, True, or 'auto', "
            f"but received {floating!r}"
        )

    args: dict[str, JSONType] = {
        "src": resolved_src,
        "controls": controls,
        "muted": muted,
        "autoplay": autoplay,
        "loop": loop,
        "rounded": rounded,
        "floating": floating_mode,
    }
    if width is not None:
        args["width"] = normalize_dimension(width)
    if height is not None:
        args["height"] = normalize_dimension(height)

    return Html(
        build_stateless_plugin(
            component_name="marimo-video",
            args=args,
        )
    )
