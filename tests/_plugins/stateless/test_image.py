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
    for fname in get_context().virtual_file_registry.registry:
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
    for fname in get_context().virtual_file_registry.registry:
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
    for fname in get_context().virtual_file_registry.registry:
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
    for fname in get_context().virtual_file_registry.registry:
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
    for fname in get_context().virtual_file_registry.registry:
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
    for fname in get_context().virtual_file_registry.registry:
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
def test_image_zero_width_array():
    import numpy as np

    with pytest.raises(ValueError, match="zero-size dimension"):
        image(np.zeros((100, 0, 3)))


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_image_uint8_no_normalization():
    import numpy as np
    from PIL import Image as PILImage

    # uint8 uniform array should not produce division-by-zero or map to 0
    arr = np.full((10, 10), 50, dtype=np.uint8)
    result = image(arr)
    assert result.text.startswith("<img src='data:image/png;base64,")
    # Decode and verify pixel values are preserved
    import base64
    import io as _io

    data_url = result.text.split("src='")[1].split("'")[0]
    b64 = data_url.split(",")[1]
    img = PILImage.open(_io.BytesIO(base64.b64decode(b64)))
    pixels = np.array(img)
    assert pixels.min() == 50
    assert pixels.max() == 50


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_image_uint8_preserves_relative_intensity():
    import base64
    import io as _io

    import numpy as np
    from PIL import Image as PILImage

    def _decode_pixels(result):
        data_url = result.text.split("src='")[1].split("'")[0]
        b64 = data_url.split(",")[1]
        img = PILImage.open(_io.BytesIO(base64.b64decode(b64)))
        return np.array(img)

    dark = np.full((10, 10), 50, dtype=np.uint8)
    light = np.full((10, 10), 200, dtype=np.uint8)
    dark_pixels = _decode_pixels(image(dark))
    light_pixels = _decode_pixels(image(light))
    # Dark image should have lower pixel values than light image
    assert dark_pixels.mean() < light_pixels.mean()


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_image_uniform_float_no_division_by_zero():
    import numpy as np

    # Uniform float array should not raise a warning or error
    arr = np.full((10, 10), 0.5, dtype=np.float32)
    result = image(arr)
    assert result.text.startswith("<img src='data:image/png;base64,")


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_image_vmin_vmax():
    import base64
    import io as _io

    import numpy as np
    from PIL import Image as PILImage

    # Float array with known range; vmin/vmax should scale correctly
    arr = np.full((10, 10), 500.0, dtype=np.float32)
    result = image(arr, vmin=0, vmax=1000)
    data_url = result.text.split("src='")[1].split("'")[0]
    b64 = data_url.split(",")[1]
    img = PILImage.open(_io.BytesIO(base64.b64decode(b64)))
    pixels = np.array(img)
    # 500 / 1000 * 255 = 127 (±1 for rounding)
    assert abs(int(pixels.mean()) - 127) <= 1


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_image_vmin_vmax_clamps():
    import base64
    import io as _io

    import numpy as np
    from PIL import Image as PILImage

    # Values outside [vmin, vmax] should be clipped
    # Row of pixels: 0, 128, 255 (grayscale 2D)
    arr = np.array([[0, 128, 255]], dtype=np.uint8)
    result = image(arr, vmin=100, vmax=200)
    data_url = result.text.split("src='")[1].split("'")[0]
    b64 = data_url.split(",")[1]
    img = PILImage.open(_io.BytesIO(base64.b64decode(b64)))
    pixels = np.array(img).flatten()
    # 0 clipped to 100 → 0; 128 → (128-100)/100*255 ≈ 71; 255 clipped to 200 → 255
    assert pixels[0] == 0
    assert pixels[2] == 255
