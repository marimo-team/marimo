# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import inspect
from typing import Literal
from unittest.mock import patch

import pytest

from marimo._plugins.stateless.video import _parse_video_timestamp, video
from marimo._plugins.ui._core.ui_element import UIElement
from marimo._runtime.context import get_context
from marimo._runtime.runtime import Kernel
from tests.conftest import ExecReqProvider


def test_video_remains_a_function() -> None:
    assert inspect.isfunction(video)


async def test_video_url() -> None:
    result = video("https://example.com/test.mp4")
    assert isinstance(result, UIElement)
    assert result.text.startswith("<marimo-ui-element ")
    assert "<marimo-video " in result.text
    assert "data-src='&quot;https://example.com/test.mp4&quot;'" in result.text
    assert "data-floating='&quot;off&quot;'" in result.text
    # External URLs are not stored as virtual files / inlined
    assert "data:" not in result.text


async def test_video_nonexistent_path_passthrough() -> None:
    # A path that isn't a readable file (e.g. a public/ file when the cwd is
    # not the notebook directory) is passed through as-is rather than inlined.
    src = "public/__marimo_test_does_not_exist__.mp4"
    result = video(src)
    assert f"data-src='&quot;{src}&quot;'" in result.text
    assert "data:" not in result.text


@pytest.mark.parametrize(
    ("floating", "mode"),
    [(True, "manual"), ("auto", "auto")],
)
async def test_video_floating(
    floating: bool | Literal["auto"],
    mode: str,
) -> None:
    result = video(
        "https://example.com/test.mp4",
        controls=False,
        muted=True,
        autoplay=True,
        loop=True,
        width=320,
        height="180px",
        rounded=True,
        floating=floating,
    )

    assert result.text.startswith("<marimo-ui-element ")
    assert "<marimo-video " in result.text
    assert "data-src='&quot;https://example.com/test.mp4&quot;'" in result.text
    assert "data-controls='false'" in result.text
    assert "data-muted='true'" in result.text
    assert "data-autoplay='true'" in result.text
    assert "data-loop='true'" in result.text
    assert "data-rounded='true'" in result.text
    assert f"data-floating='&quot;{mode}&quot;'" in result.text
    assert "data-width='&quot;320px&quot;'" in result.text
    assert "data-height='&quot;180px&quot;'" in result.text


async def test_video_rejects_invalid_floating_mode() -> None:
    with pytest.raises(ValueError, match="floating must be"):
        video(
            "https://example.com/test.mp4",
            floating="always",  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    ("timestamp", "seconds"),
    [
        (97, 97.0),
        (97.25, 97.25),
        ("1:37", 97.0),
        ("01:37.5", 97.5),
        ("1:02:03", 3723.0),
        ("60:00", 3600.0),
    ],
)
def test_parse_video_timestamp(
    timestamp: float | str,
    seconds: float,
) -> None:
    assert _parse_video_timestamp(timestamp) == seconds


@pytest.mark.parametrize(
    "timestamp",
    [True, -1, float("inf"), float("nan"), "97", "1:60", "1:60:00", "x:y"],
)
def test_parse_video_timestamp_rejects_invalid_values(
    timestamp: object,
) -> None:
    with pytest.raises((TypeError, ValueError)):
        _parse_video_timestamp(timestamp)  # type: ignore[arg-type]


def test_video_seek_sends_command() -> None:
    player = video("https://example.com/test.mp4")

    with patch.object(player, "_send_message") as send_message:
        player.seek("1:37")

    send_message.assert_called_once_with(
        {"type": "seek", "time": 97.0},
        buffers=None,
    )


async def test_video_bytes(k: Kernel, exec_req: ExecReqProvider) -> None:
    await k.run(
        [
            exec_req.get(
                """
                import marimo as mo
                video = mo.video(b"hello")
                """
            ),
        ]
    )
    assert len(get_context().virtual_file_registry.registry) == 1
    for fname in get_context().virtual_file_registry.registry:
        assert fname.endswith(".mp4")


async def test_video_bytes_io(k: Kernel, exec_req: ExecReqProvider) -> None:
    await k.run(
        [
            exec_req.get(
                """
                import io
                import marimo as mo
                bytestream = io.BytesIO(b"hello")
                video = mo.video(bytestream)
                """
            ),
        ]
    )
    assert len(get_context().virtual_file_registry.registry) == 1
    for fname in get_context().virtual_file_registry.registry:
        assert fname.endswith(".mp4")


async def test_video_local_file(k: Kernel, exec_req: ExecReqProvider) -> None:
    # A local file is stored as a virtual file (and served via a URL) rather
    # than being inlined into the output as a base64 data URL. This is what
    # keeps large videos from blowing past the output size limit.
    await k.run(
        [
            exec_req.get(
                """
                import os
                import marimo as mo
                with open("test_video.mp4", "wb") as f:
                    f.write(b"fake video bytes")
                video = mo.video("test_video.mp4")
                os.remove("test_video.mp4")
                """
            ),
        ]
    )
    assert len(get_context().virtual_file_registry.registry) == 1
    for fname in get_context().virtual_file_registry.registry:
        assert fname.endswith(".mp4")
    # The resolved src is a virtual-file URL, not an inline data URL.
    video_html = k.globals["video"]
    assert "data:" not in video_html.text
    assert "@file/" in video_html.text
