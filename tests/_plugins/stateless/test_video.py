# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import sys

import pytest

from marimo._plugins.stateless.video import video
from marimo._runtime.context import get_context
from marimo._runtime.runtime import Kernel
from tests.conftest import ExecReqProvider


async def test_video_url() -> None:
    result = video("https://example.com/test.mp4")
    assert "src='https://example.com/test.mp4'" in result.text
    # External URLs are not stored as virtual files / inlined
    assert "data:" not in result.text


async def test_video_nonexistent_path_passthrough() -> None:
    # A path that isn't a readable file (e.g. a public/ file when the cwd is
    # not the notebook directory) is passed through as-is rather than inlined.
    src = "public/__marimo_test_does_not_exist__.mp4"
    result = video(src)
    assert f"src='{src}'" in result.text
    assert "data:" not in result.text


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


@pytest.mark.skipif(sys.platform == "win32", reason="Failing on Windows CI")
async def test_video_local_file(k: Kernel, exec_req: ExecReqProvider) -> None:
    # A local file is stored as a virtual file (and served via a URL) rather
    # than being inlined into the output as a base64 data URL. This is what
    # keeps large videos from blowing past the output size limit.
    with open(__file__, encoding="utf-8") as f:  # noqa: ASYNC230
        await k.run(
            [
                exec_req.get(
                    f"""
                    import marimo as mo
                    video = mo.video('{f.name}')
                    """
                ),
            ]
        )
        assert len(get_context().virtual_file_registry.registry) == 1
        for fname in get_context().virtual_file_registry.registry:
            assert fname.endswith(".py")


async def test_video_local_file_not_inlined(
    k: Kernel, exec_req: ExecReqProvider
) -> None:
    # The resolved src should be a virtual-file URL, not an inline data URL.
    await k.run(
        [
            exec_req.get(
                f"""
                import marimo as mo
                video = mo.video('{__file__}')
                """
            ),
        ]
    )
    video_html = k.globals["video"]
    assert "data:" not in video_html.text
    assert "@file/" in video_html.text
