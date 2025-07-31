# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import sys

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins.stateless.image_compare import image_compare
from marimo._runtime.context import get_context
from marimo._runtime.runtime import Kernel
from tests.conftest import ExecReqProvider

HAS_DEPS = DependencyManager.numpy.has() and DependencyManager.pillow.has()


async def test_image_compare_basic() -> None:
    result = image_compare(
        before_image="https://marimo.io/logo.png",
        after_image="https://marimo.io/logo.png",
    )
    assert "marimo-image-comparison" in result.text
    assert "before-src" in result.text
    assert "after-src" in result.text
    assert "value" in result.text
    assert "direction" in result.text


async def test_image_compare_with_value() -> None:
    result = image_compare(
        before_image="https://marimo.io/logo.png",
        after_image="https://marimo.io/logo.png",
        value=75,
    )
    assert "marimo-image-comparison" in result.text
    assert "data-value='75.0'" in result.text


async def test_image_compare_vertical() -> None:
    result = image_compare(
        before_image="https://marimo.io/logo.png",
        after_image="https://marimo.io/logo.png",
        direction="vertical",
    )
    assert "marimo-image-comparison" in result.text
    assert "data-direction='&quot;vertical&quot;'" in result.text


async def test_image_compare_with_dimensions() -> None:
    result = image_compare(
        before_image="https://marimo.io/logo.png",
        after_image="https://marimo.io/logo.png",
        width=500,
        height=400,
    )
    assert "marimo-image-comparison" in result.text
    assert "data-width='&quot;500px&quot;'" in result.text
    assert "data-height='&quot;400px&quot;'" in result.text


async def test_image_compare_with_string_dimensions() -> None:
    result = image_compare(
        before_image="https://marimo.io/logo.png",
        after_image="https://marimo.io/logo.png",
        width="50%",
        height="300px",
    )
    assert "marimo-image-comparison" in result.text
    assert "data-width='&quot;50%&quot;'" in result.text
    assert "data-height='&quot;300px&quot;'" in result.text


async def test_image_compare_value_bounds() -> None:
    # Test value below 0
    result = image_compare(
        before_image="https://marimo.io/logo.png",
        after_image="https://marimo.io/logo.png",
        value=-10,
    )
    assert "data-value='0'" in result.text

    # Test value above 100
    result = image_compare(
        before_image="https://marimo.io/logo.png",
        after_image="https://marimo.io/logo.png",
        value=150,
    )
    assert "data-value='100'" in result.text


async def test_image_compare_filename(
    k: Kernel, exec_req: ExecReqProvider
) -> None:
    await k.run(
        [
            exec_req.get(
                """
                import marimo as mo
                import os
                # Create test images
                with open("test_before.png", "wb") as f:
                    f.write(b"before_image_data")
                with open("test_after.png", "wb") as f:
                    f.write(b"after_image_data")

                comparison = mo.image_compare("test_before.png", "test_after.png")

                # Clean up
                os.remove("test_before.png")
                os.remove("test_after.png")
                """
            ),
        ]
    )

    assert len(get_context().virtual_file_registry.registry) == 2
    for fname in get_context().virtual_file_registry.registry.keys():
        assert fname.endswith(".png")


async def test_image_compare_path(
    k: Kernel, exec_req: ExecReqProvider
) -> None:
    await k.run(
        [
            exec_req.get(
                """
                import marimo as mo
                from pathlib import Path
                import os

                # Create test images
                with open("test_before.png", "wb") as f:
                    f.write(b"before_image_data")
                with open("test_after.png", "wb") as f:
                    f.write(b"after_image_data")

                comparison = mo.image_compare(
                    Path("test_before.png"),
                    Path("test_after.png")
                )

                # Clean up
                os.remove("test_before.png")
                os.remove("test_after.png")
                """
            ),
        ]
    )

    assert len(get_context().virtual_file_registry.registry) == 2
    for fname in get_context().virtual_file_registry.registry.keys():
        assert fname.endswith(".png")


async def test_image_compare_bytes_io(
    k: Kernel, exec_req: ExecReqProvider
) -> None:
    await k.run(
        [
            exec_req.get(
                """
                import io
                import marimo as mo

                before_stream = io.BytesIO(b"before_image_data")
                after_stream = io.BytesIO(b"after_image_data")
                comparison = mo.image_compare(before_stream, after_stream)
                """
            ),
        ]
    )

    assert len(get_context().virtual_file_registry.registry) == 2
    for fname in get_context().virtual_file_registry.registry.keys():
        assert fname.endswith(".png")


async def test_image_compare_mixed_sources(
    k: Kernel, exec_req: ExecReqProvider
) -> None:
    await k.run(
        [
            exec_req.get(
                """
                import io
                import marimo as mo
                import os

                # Create one file
                with open("test_before.png", "wb") as f:
                    f.write(b"before_image_data")

                # Use file for before, BytesIO for after
                after_stream = io.BytesIO(b"after_image_data")
                comparison = mo.image_compare("test_before.png", after_stream)

                # Clean up
                os.remove("test_before.png")
                """
            ),
        ]
    )

    assert len(get_context().virtual_file_registry.registry) == 2


async def test_image_compare_str(k: Kernel, exec_req: ExecReqProvider) -> None:
    await k.run(
        [
            exec_req.get(
                """
                import marimo as mo
                comparison = mo.image_compare(
                    "https://marimo.io/logo.png",
                    "https://marimo.io/logo.png"
                )
                """
            ),
        ]
    )

    # URLs should not be registered
    assert len(get_context().virtual_file_registry.registry) == 0


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
async def test_image_compare_array(
    k: Kernel, exec_req: ExecReqProvider
) -> None:
    await k.run(
        [
            exec_req.get(
                """
                import marimo as mo

                before_data = [[[255, 0, 0], [0, 255, 0], [0, 0, 255]]]
                after_data = [[[0, 255, 0], [255, 0, 0], [0, 0, 255]]]
                comparison = mo.image_compare(before_data, after_data)
                """
            ),
        ]
    )

    assert len(get_context().virtual_file_registry.registry) == 2
    for fname in get_context().virtual_file_registry.registry.keys():
        assert fname.endswith(".png")


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
async def test_image_compare_numpy(
    k: Kernel, exec_req: ExecReqProvider
) -> None:
    await k.run(
        [
            exec_req.get(
                """
                import marimo as mo
                import numpy as np

                before_data = np.random.rand(10, 10, 3)
                after_data = np.random.rand(10, 10, 3)
                comparison = mo.image_compare(before_data, after_data)
                """
            ),
        ]
    )

    assert len(get_context().virtual_file_registry.registry) == 2
    for fname in get_context().virtual_file_registry.registry.keys():
        assert fname.endswith(".png")


@pytest.mark.skipif(sys.platform == "win32", reason="Failing on Windows CI")
async def test_image_compare_local_file(
    k: Kernel, exec_req: ExecReqProvider
) -> None:
    # Use this test file itself as a dummy image
    with open(__file__, encoding="utf-8") as f:  # noqa: ASYNC230
        await k.run(
            [
                exec_req.get(
                    f"""
                    import marimo as mo
                    comparison = mo.image_compare('{f.name}', '{f.name}')
                    """
                ),
            ]
        )
        assert len(get_context().virtual_file_registry.registry) == 2


async def test_image_compare_error_handling() -> None:
    # This should not raise an exception, but handle the error gracefully
    result = image_compare(
        before_image="invalid_path_that_does_not_exist.png",
        after_image="another_invalid_path.png",
    )

    # Should still generate HTML even with invalid images
    assert "marimo-image-comparison" in result.text
