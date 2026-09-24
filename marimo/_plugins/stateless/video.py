# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import io
import math
import os
import re
from typing import Literal

import marimo._output.data.data as mo_data
from marimo._output.rich_help import mddoc
from marimo._output.utils import normalize_dimension
from marimo._plugins.core.media import io_to_data_url
from marimo._plugins.core.web_component import JSONType
from marimo._plugins.ui._core.ui_element import UIElement

_TIMESTAMP_PATTERN = re.compile(
    r"^(?:(?P<hours>\d+):)?(?P<minutes>\d+):(?P<seconds>\d+(?:\.\d+)?)$"
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


def _parse_video_timestamp(timestamp: float | str) -> float:
    if isinstance(timestamp, bool):
        raise TypeError("timestamp must be a number of seconds or a timestamp")

    if isinstance(timestamp, (int, float)):
        seconds = float(timestamp)
    elif isinstance(timestamp, str):
        match = _TIMESTAMP_PATTERN.fullmatch(timestamp.strip())
        if match is None:
            raise ValueError(
                "timestamp must use MM:SS or HH:MM:SS format, "
                f"but received {timestamp!r}"
            )

        hours_text = match.group("hours")
        hours = int(hours_text) if hours_text is not None else 0
        minutes = int(match.group("minutes"))
        component_seconds = float(match.group("seconds"))
        if component_seconds >= 60 or (
            hours_text is not None and minutes >= 60
        ):
            raise ValueError(f"invalid video timestamp: {timestamp!r}")
        seconds = hours * 3600 + minutes * 60 + component_seconds
    else:
        raise TypeError("timestamp must be a number of seconds or a timestamp")

    if not math.isfinite(seconds) or seconds < 0:
        raise ValueError("timestamp must be a finite, non-negative duration")
    return seconds


class _Video(UIElement[None, None]):
    def __init__(self, args: dict[str, JSONType]) -> None:
        super().__init__(
            component_name="marimo-video",
            initial_value=None,
            label=None,
            args=args,
            on_change=None,
        )

    def _convert_value(self, value: None) -> None:
        return value

    def seek(self, timestamp: float | str) -> None:
        """Seek to a timestamp without changing the playback state.

        Args:
            timestamp: a non-negative number of seconds, or a timestamp in
                `MM:SS` or `HH:MM:SS` format.
        """
        self._send_message(
            {"type": "seek", "time": _parse_video_timestamp(timestamp)},
            buffers=None,
        )


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
) -> _Video:
    """Render a video as HTML.

    Example:
        ```python3
        # Render a video from a URL
        mo.video(src="https://docs.marimo.io/_static/readme-ui.mp4")

        # Render a video from a local file
        mo.video(src="path/to/video.mp4")

        # Let the video follow the reader as they scroll
        mo.video(src="path/to/video.mp4", floating="auto")

        # In one cell, create and display the player
        player = mo.video(src="path/to/video.mp4", floating="auto")
        player

        # In a second cell, add a chapter button
        jump_to_chapter = mo.ui.run_button(label="Jump to chapter")
        jump_to_chapter

        # In a third cell, react to the interaction
        mo.stop(not jump_to_chapter.value)
        player.seek("1:37")
        ```

    Args:
        src: the URL of the video, a path to a local file, `bytes`, or a
            file-like object opened in binary mode.
        controls: whether to show the controls.
        muted: whether to mute the video.
        autoplay: whether to autoplay the video. The video will only autoplay
            if `muted` is `True`.
        loop: whether to loop the video.
        width: the width of the video in pixels or a string with units.
        height: the height of the video in pixels or a string with units.
        rounded: whether to round the corners of the video.
        floating: whether the video can float above the notebook. `True` adds
            a button for moving the video between its inline and floating
            positions. `"auto"` also floats the video after it has been visible
            and is then scrolled out of view. Drag the floating video to move
            it between corners, or drag its inward corner to resize it.
            Floating uses an in-page panel, not the browser's Picture-in-Picture
            API.

    Methods:
        seek(timestamp): seek to a timestamp given in seconds, `MM:SS`, or
            `HH:MM:SS` format.
    """
    if floating is False:
        floating_mode = "off"
    elif floating is True:
        floating_mode = "manual"
    elif floating == "auto":
        floating_mode = "auto"
    else:
        raise ValueError(
            "floating must be False, True, or 'auto', "
            f"but received {floating!r}"
        )

    args: dict[str, JSONType] = {
        "src": _get_resolved_src(src),
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

    return _Video(args)
