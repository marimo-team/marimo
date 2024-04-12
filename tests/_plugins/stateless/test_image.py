# Copyright 2024 Marimo. All rights reserved.
import sys

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins.stateless.image import image
from marimo._runtime.context import get_context
from marimo._runtime.runtime import Kernel
from tests.conftest import ExecReqProvider

HAS_DEPS = DependencyManager.has_numpy() and DependencyManager.has_pillow()


async def test_image() -> None:
    result = image(
        "https://marimo.io/logo.png",
    )
    assert result.text == "<img src='https://marimo.io/logo.png' />"


async def test_image_bytes_io(k: Kernel, exec_req: ExecReqProvider) -> None:
    await k.run(
        [
            exec_req.get(
                """
                import io
                import marimo as mo
                bytestream = io.BytesIO(b"hello")
                image = mo.image(bytestream)
                """
            ),
        ]
    )
    assert len(get_context().virtual_file_registry.registry) == 1
    for fname, _ in get_context().virtual_file_registry.registry.items():
        assert fname.endswith(".png")


async def test_image_bytes(k: Kernel, exec_req: ExecReqProvider) -> None:
    await k.run(
        [
            exec_req.get(
                """
                import io
                import marimo as mo
                bytestream = io.BytesIO(b"hello")
                image = mo.image(bytestream)
                """
            ),
        ]
    )
    assert len(get_context().virtual_file_registry.registry) == 1
    for fname, _ in get_context().virtual_file_registry.registry.items():
        assert fname.endswith(".png")


async def test_image_str(k: Kernel, exec_req: ExecReqProvider) -> None:
    await k.run(
        [
            exec_req.get(
                """
                import marimo as mo
                image = mo.image("https://marimo.io/logo.png")
                """
            ),
        ]
    )
    assert len(get_context().virtual_file_registry.registry) == 0


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
async def test_image_array(k: Kernel, exec_req: ExecReqProvider) -> None:
    await k.run(
        [
            exec_req.get(
                """
                import marimo as mo
                data = [[[255, 0, 0], [0, 255, 0], [0, 0, 255]]]
                image = mo.image(data)
                """
            ),
        ]
    )
    assert len(get_context().virtual_file_registry.registry) == 1
    for fname, _ in get_context().virtual_file_registry.registry.items():
        assert fname.endswith(".png")


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
async def test_image_numpy(k: Kernel, exec_req: ExecReqProvider) -> None:
    await k.run(
        [
            exec_req.get(
                """
                import marimo as mo
                import numpy as np
                data = np.random.rand(10, 10)
                image = mo.image(data)
                """
            ),
        ]
    )
    assert len(get_context().virtual_file_registry.registry) == 1
    for fname, _ in get_context().virtual_file_registry.registry.items():
        assert fname.endswith(".png")


# TODO(akshayka): Debug on Windows
@pytest.mark.skipif(sys.platform == "win32", reason="Failing on Windows CI")
async def test_image_local_file(k: Kernel, exec_req: ExecReqProvider) -> None:
    # Just opens a file that exists, and make sure it gets registered
    # in the virtual path registry
    with open(__file__, encoding="utf-8") as f:  # noqa: ASYNC101
        await k.run(
            [
                exec_req.get(
                    f"""
                    import marimo as mo
                    image = mo.image('{f.name}')
                    """
                ),
            ]
        )
        assert len(get_context().virtual_file_registry.registry) == 1
