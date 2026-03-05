# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import io
import sys
from typing import TYPE_CHECKING

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins.stateless.image import image
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


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_image_normalize_flag():
    """Test that normalize=False preserves original pixel values."""
    import numpy as np
    from PIL import Image as PILImage

    dark = np.full((10, 10), 50, dtype=np.uint8)
    light = np.full((10, 10), 200, dtype=np.uint8)

    # With normalize=True (default), both images are rescaled to 0-255 range.
    # Since each is a constant image, there is no min/max spread to rescale,
    # but the important test is that normalize=False gives different results.
    result_dark_norm = image(dark, normalize=True)
    result_light_norm = image(light, normalize=True)

    # With normalize=False, pixel values are preserved as-is.
    result_dark_raw = image(dark, normalize=False)
    result_light_raw = image(light, normalize=False)

    # Decode the images and verify pixel values are preserved
    # when normalize=False.
    import base64
    import re

    def _decode_image(html_text: str) -> np.ndarray:
        match = re.search(r"base64,([^']+)", html_text)
        assert match, f"No base64 data found in {html_text[:100]}"
        data = base64.b64decode(match.group(1))
        img = PILImage.open(io.BytesIO(data))
        return np.array(img)

    dark_pixels = _decode_image(result_dark_raw.text)
    light_pixels = _decode_image(result_light_raw.text)

    # Without normalization, pixel values should be preserved.
    assert np.all(dark_pixels == 50), (
        f"Expected all pixels == 50, got unique values: {np.unique(dark_pixels)}"
    )
    assert np.all(light_pixels == 200), (
        f"Expected all pixels == 200, got unique values: {np.unique(light_pixels)}"
    )


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_image_normalize_constant_image():
    """Test that normalize=True handles constant images without errors."""
    import numpy as np

    # A constant image should not cause division by zero
    constant = np.full((10, 10), 128, dtype=np.uint8)
    result = image(constant, normalize=True)
    assert result.text.startswith("<img src='data:image/png;base64,")
