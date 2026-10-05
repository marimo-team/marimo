# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import base64
import io
import sys
import wave

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
    for fname in get_context().virtual_file_registry.registry:
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
    for fname in get_context().virtual_file_registry.registry:
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
    for fname in get_context().virtual_file_registry.registry:
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
    for fname in get_context().virtual_file_registry.registry:
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
    for fname in get_context().virtual_file_registry.registry:
        assert fname.endswith(".wav")


@pytest.mark.skipif(not HAS_NUMPY, reason="numpy not installed")
async def test_audio_numpy_constructor() -> None:
    import numpy as np

    # Rate
    data = np.random.rand(1000) * 2 - 1  # Random values between -1 and 1
    res = audio(data, rate=44100, normalize=False)
    assert res.text.startswith("<audio src='data:audio/")

    # Don't normalize out of range
    data = np.random.rand(1000) * 10  # Values > 1
    with pytest.raises(ValueError):
        res = audio(data, rate=44100, normalize=False)

    # Normalize in range
    data = np.random.rand(1000) * 10  # Values > 1
    res = audio(data, rate=44100, normalize=True)

    # No rate
    with pytest.raises(ValueError):
        res = audio(data)


@pytest.mark.skipif(not HAS_NUMPY, reason="numpy not installed")
@pytest.mark.parametrize("channels", [1, 2])
@pytest.mark.parametrize("normalize", [True, False])
def test_audio_numpy_silence(channels: int, normalize: bool) -> None:
    import numpy as np

    samples = 8
    shape = (samples,) if channels == 1 else (channels, samples)
    with np.errstate(invalid="raise", divide="raise"):
        result = audio(np.zeros(shape), rate=44100, normalize=normalize)

    encoded = result.text.split("base64,", 1)[1].split("'", 1)[0]
    with wave.open(io.BytesIO(base64.b64decode(encoded)), "rb") as wav:
        assert tuple(wav.getparams()) == (
            channels,
            2,
            44100,
            samples,
            "NONE",
            "not compressed",
        )
        assert wav.readframes(samples) == b"\x00\x00" * channels * samples


@pytest.mark.skipif(sys.platform == "win32", reason="Failing on Windows CI")
async def test_audio_local_file(k: Kernel, exec_req: ExecReqProvider) -> None:
    with open(__file__, encoding="utf-8") as f:  # noqa: ASYNC230
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
