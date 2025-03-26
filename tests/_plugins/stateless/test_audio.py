# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import sys

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins.stateless.audio import audio
from marimo._runtime.context import get_context
from marimo._runtime.runtime import Kernel
from tests.conftest import ExecReqProvider

HAS_NUMPY = DependencyManager.numpy.has()


async def test_audio_url() -> None:
    result = audio("https://example.com/test.wav")
    assert (
        result.text
        == "<audio src='https://example.com/test.wav' controls></audio>"
    )


async def test_audio_filename(k: Kernel, exec_req: ExecReqProvider) -> None:
    await k.run(
        [
            exec_req.get(
                """
                import marimo as mo
                import os
                with open("test_audio.wav", "wb") as f:
                    f.write(b"hello")
                audio = mo.audio("test_audio.wav")
                # Delete the file
                os.remove("test_audio.wav")
                """
            ),
        ]
    )
    assert len(get_context().virtual_file_registry.registry) == 1
    for fname in get_context().virtual_file_registry.registry.keys():
        assert fname.endswith(".wav")


async def test_audio_bytes_io(k: Kernel, exec_req: ExecReqProvider) -> None:
    await k.run(
        [
            exec_req.get(
                """
                import io
                import marimo as mo
                bytestream = io.BytesIO(b"hello")
                audio = mo.audio(bytestream)
                """
            ),
        ]
    )
    assert len(get_context().virtual_file_registry.registry) == 1
    for fname in get_context().virtual_file_registry.registry.keys():
        assert fname.endswith(".wav")


async def test_audio_bytes(k: Kernel, exec_req: ExecReqProvider) -> None:
    await k.run(
        [
            exec_req.get(
                """
                import marimo as mo
                audio = mo.audio(b"hello")
                """
            ),
        ]
    )
    assert len(get_context().virtual_file_registry.registry) == 1
    for fname in get_context().virtual_file_registry.registry.keys():
        assert fname.endswith(".wav")


@pytest.mark.skipif(not HAS_NUMPY, reason="numpy not installed")
async def test_audio_numpy_mono(k: Kernel, exec_req: ExecReqProvider) -> None:
    await k.run(
        [
            exec_req.get(
                """
                import marimo as mo
                import numpy as np
                data = np.random.rand(1000) * 2 - 1  # Random values between -1 and 1
                audio = mo.audio(data, rate=44100)
                """
            ),
        ]
    )
    assert len(get_context().virtual_file_registry.registry) == 1
    for fname in get_context().virtual_file_registry.registry.keys():
        assert fname.endswith(".wav")


@pytest.mark.skipif(not HAS_NUMPY, reason="numpy not installed")
async def test_audio_numpy_stereo(
    k: Kernel, exec_req: ExecReqProvider
) -> None:
    await k.run(
        [
            exec_req.get(
                """
                import marimo as mo
                import numpy as np
                data = np.random.rand(2, 1000) * 2 - 1  # Random values between -1 and 1
                audio = mo.audio(data, rate=44100)
                """
            ),
        ]
    )
    assert len(get_context().virtual_file_registry.registry) == 1
    for fname in get_context().virtual_file_registry.registry.keys():
        assert fname.endswith(".wav")


@pytest.mark.skipif(not HAS_NUMPY, reason="numpy not installed")
async def test_audio_numpy_normalize(
    k: Kernel, exec_req: ExecReqProvider
) -> None:
    await k.run(
        [
            exec_req.get(
                """
                import marimo as mo
                import numpy as np
                data = np.random.rand(1000) * 10  # Values > 1
                audio = mo.audio(data, rate=44100, normalize=True)
                """
            ),
        ]
    )
    assert len(get_context().virtual_file_registry.registry) == 1
    for fname in get_context().virtual_file_registry.registry.keys():
        assert fname.endswith(".wav")


@pytest.mark.skipif(not HAS_NUMPY, reason="numpy not installed")
async def test_audio_numpy_no_normalize(
    k: Kernel, exec_req: ExecReqProvider
) -> None:
    await k.run(
        [
            exec_req.get(
                """
                  import marimo as mo
                  import numpy as np
                  data = np.random.rand(1000) * 10  # Values > 1
                  audio = mo.audio(data, rate=44100, normalize=False)
                  """
            ),
        ]
    )


@pytest.mark.skipif(not HAS_NUMPY, reason="numpy not installed")
async def test_audio_numpy_no_rate(
    k: Kernel, exec_req: ExecReqProvider
) -> None:
    await k.run(
        [
            exec_req.get(
                """
                  import marimo as mo
                  import numpy as np
                  data = np.random.rand(1000)
                  audio = mo.audio(data)
                  """
            ),
        ]
    )


@pytest.mark.skipif(sys.platform == "win32", reason="Failing on Windows CI")
async def test_audio_local_file(k: Kernel, exec_req: ExecReqProvider) -> None:
    with open(__file__, encoding="utf-8") as f:  # noqa: ASYNC101 ASYNC230
        await k.run(
            [
                exec_req.get(
                    f"""
                    import marimo as mo
                    audio = mo.audio('{f.name}')
                    """
                ),
            ]
        )
        assert len(get_context().virtual_file_registry.registry) == 1
