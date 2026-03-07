# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import io
import sys
from typing import TYPE_CHECKING

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins.stateless.image import _normalize_image, image
from marimo._runtime.context import get_context
from marimo._runtime.runtime import Kernel
from tests.conftest import ExecReqProvider

HAS_DEPS = DependencyManager.numpy.has() and DependencyManager.pillow.has()

if TYPE_CHECKING:
    from pathlib import Path


async def test_image() -> None:
    result = image(
        "https://marimo.io/logo.png",
    )
    assert result.text == "<img src='https://marimo.io/logo.png' />"


async def test_image_filename(k: Kernel, exec_req: ExecReqProvider) -> None:
    await k.run(
        [
            exec_req.get(
                """
                import marimo as mo
                import os
                with open("test_image.png", "wb") as f:
                    f.write(b"hello")
                image = mo.image("test_image.png")
                # Delete the file
                os.remove("test_image.png")
                """
            ),
        ]
    )

    assert len(get_context().virtual_file_registry.registry) == 1
    for fname in get_context().virtual_file_registry.registry.keys():
        assert fname.endswith(".png")


async def test_image_path(k: Kernel, exec_req: ExecReqProvider) -> None:
    await k.run(
        [
            exec_req.get(
                """
                import marimo as mo
                from pathlib import Path
                import os
                # Create the image file
                with open("test_image.png", "wb") as f:
                    f.write(b"hello")
                image = mo.image(Path("test_image.png"))
                # Delete the file
                os.remove("test_image.png")
                """
            ),
        ]
    )
    assert len(get_context().virtual_file_registry.registry) == 1
    for fname in get_context().virtual_file_registry.registry.keys():
        assert fname.endswith(".png")


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
    for fname in get_context().virtual_file_registry.registry.keys():
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
    for fname in get_context().virtual_file_registry.registry.keys():
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
    for fname in get_context().virtual_file_registry.registry.keys():
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
    for fname in get_context().virtual_file_registry.registry.keys():
        assert fname.endswith(".png")


# TODO(akshayka): Debug on Windows
@pytest.mark.skipif(sys.platform == "win32", reason="Failing on Windows CI")
async def test_image_local_file(k: Kernel, exec_req: ExecReqProvider) -> None:
    # Just opens a file that exists, and make sure it gets registered
    # in the virtual path registry
    with open(__file__, encoding="utf-8") as f:  # noqa: ASYNC230
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


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_normalize_image_constant_array_preserves_values() -> None:
    import numpy as np
    from PIL import Image as PILImage

    normalized = _normalize_image(np.full((4, 4), 50, dtype=np.uint8))
    assert isinstance(normalized, io.BytesIO)

    normalized.seek(0)
    pixel_values = np.asarray(PILImage.open(normalized))
    assert pixel_values.min() == 50
    assert pixel_values.max() == 50


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_normalize_image_can_be_disabled() -> None:
    import numpy as np
    from PIL import Image as PILImage

    normalized = _normalize_image(
        np.array([[10.0, 20.0], [30.0, 40.0]]),
        normalize=False,
    )
    normalized.seek(0)

    pixel_values = np.asarray(PILImage.open(normalized))
    assert pixel_values.tolist() == [[10, 20], [30, 40]]


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_normalize_image_with_vmin_vmax() -> None:
    import numpy as np
    from PIL import Image as PILImage

    normalized = _normalize_image(
        np.array([[50.0, 200.0]]),
        vmin=0,
        vmax=255,
    )
    normalized.seek(0)

    pixel_values = np.asarray(PILImage.open(normalized))
    assert pixel_values.tolist() == [[50, 200]]


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_normalize_image_rejects_vmin_vmax_without_normalization() -> None:
    import numpy as np

    with pytest.raises(ValueError, match="normalize=True"):
        _normalize_image(np.array([[1.0, 2.0]]), normalize=False, vmin=0)


def test_image_constructor(tmp_path: Path):
    # BytesIO
    result = image(
        io.BytesIO(b"hello"),
    )
    assert result.text.startswith("<img src='data:image/png;base64,")
    # Bytes
    result = image(
        io.BytesIO(b"hello").getvalue(),
    )
    assert result.text.startswith("<img src='data:image/png;base64,")
    # String
    result = image(
        "https://marimo.io/logo.png",
    )
    assert result.text.startswith("<img src='https://marimo.io/logo.png' />")
    # Path
    img_path = tmp_path / "test.png"
    img_path.touch()
    result = image(img_path)
    assert result.text.startswith("<img src='data:image/png;base64,")


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_image_constructor_pil():
    from PIL import Image

    # PIL Image
    result = image(
        Image.new("RGB", (100, 100), color="red"),
    )
    assert result.text.startswith("<img src='data:image/png;base64,")
