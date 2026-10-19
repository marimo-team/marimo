# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from pathlib import Path

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


async def test_video_pathlib_nonexistent_passthrough() -> None:
    src = Path("public/__marimo_test_does_not_exist__.mp4")
    result = video(src)
    assert f"src='{src.as_posix()}'" in result.text
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


async def test_video_pathlib_path(
    k: Kernel, exec_req: ExecReqProvider
) -> None:
    await k.run(
        [
            exec_req.get(
                """
                import os
                from pathlib import Path
                import marimo as mo
                with open("test_video.mp4", "wb") as f:
                    f.write(b"fake video bytes")
                video = mo.video(Path("test_video.mp4"))
                os.remove("test_video.mp4")
                """
            ),
        ]
    )
    assert len(get_context().virtual_file_registry.registry) == 1
    for fname in get_context().virtual_file_registry.registry:
        assert fname.endswith(".mp4")
    video_html = k.globals["video"]
    assert "data:" not in video_html.text
    assert "@file/" in video_html.text


@pytest.mark.parametrize(
    ("filename", "expected_ext"),
    [
        ("test_video.webm", ".webm"),
        ("test_video_no_ext", ".mp4"),
    ],
)
async def test_video_pathlib_variations(
    k: Kernel,
    exec_req: ExecReqProvider,
    filename: str,
    expected_ext: str,
) -> None:
    await k.run(
        [
            exec_req.get(
                f"""
                import os
                from pathlib import Path
                import marimo as mo
                with open("{filename}", "wb") as f:
                    f.write(b"fake video bytes")
                video = mo.video(Path("{filename}"))
                os.remove("{filename}")
                """
            ),
        ]
    )
    assert len(get_context().virtual_file_registry.registry) == 1
    for fname in get_context().virtual_file_registry.registry:
        assert fname.endswith(expected_ext)
    video_html = k.globals["video"]
    assert "data:" not in video_html.text
    assert "@file/" in video_html.text


async def test_video_pathlib_home_expansion(
    k: Kernel,
    exec_req: ExecReqProvider,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake_home = tmp_path / "fake_home"
    fake_home.mkdir()
    sample = fake_home / "sample.mp4"
    sample.write_bytes(b"fake video bytes")
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setenv("USERPROFILE", str(fake_home))
    await k.run(
        [
            exec_req.get(
                """
                from pathlib import Path
                import marimo as mo
                video = mo.video(Path("~/sample.mp4"))
                """
            ),
        ]
    )
    assert len(get_context().virtual_file_registry.registry) == 1
    for fname in get_context().virtual_file_registry.registry:
        assert fname.endswith(".mp4")
    video_html = k.globals["video"]
    assert "data:" not in video_html.text
    assert "@file/" in video_html.text


async def test_video_pathlib_real_media(
    k: Kernel, exec_req: ExecReqProvider, tmp_path: Path
) -> None:
    real_video = tmp_path / "real_video.mp4"
    real_video.write_bytes(
        b"\x00\x00\x00\x1cftypisom\x00\x00\x02\x00isomiso2mp41\x00\x00\x00\x08free"
    )
    await k.run(
        [
            exec_req.get(
                f"""
                from pathlib import Path
                import marimo as mo
                video = mo.video(Path(r"{real_video.as_posix()}"))
                """
            ),
        ]
    )
    assert len(get_context().virtual_file_registry.registry) == 1
    for fname in get_context().virtual_file_registry.registry:
        assert fname.endswith(".mp4")
    video_html = k.globals["video"]
    assert "data:" not in video_html.text
    assert "@file/" in video_html.text
