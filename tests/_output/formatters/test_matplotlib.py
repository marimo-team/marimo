from __future__ import annotations

import base64
import json
import struct

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._runtime.runtime import Kernel
from tests.conftest import ExecReqProvider

HAS_MPL = DependencyManager.matplotlib.has()


@pytest.mark.skipif(not HAS_MPL, reason="optional dependencies not installed")
async def test_matplotlib_rc_light(
    executing_kernel: Kernel, exec_req: ExecReqProvider
) -> None:
    import matplotlib.pyplot as plt  # type: ignore

    from marimo._output.formatters.formatters import register_formatters

    plt.rcParams["font.family"] = ["monospace"]

    register_formatters(theme="light")

    await executing_kernel.run(
        [
            exec_req.get(
                """
                import matplotlib.pyplot as plt

                rcParams = plt.rcParams
                """
            )
        ]
    )

    rcParams = executing_kernel.globals["rcParams"]
    assert rcParams["font.family"] == ["monospace"]
    assert rcParams["figure.facecolor"] == "white"


@pytest.mark.skipif(not HAS_MPL, reason="optional dependencies not installed")
async def test_matplotlib_rc_dark(
    executing_kernel: Kernel, exec_req: ExecReqProvider
) -> None:
    import matplotlib.pyplot as plt  # type: ignore

    from marimo._output.formatters.formatters import register_formatters

    plt.rcParams["font.family"] = ["monospace"]

    register_formatters(theme="dark")

    await executing_kernel.run(
        [
            exec_req.get(
                """
                import matplotlib.pyplot as plt

                rcParams = plt.rcParams
                """
            )
        ]
    )

    rcParams = executing_kernel.globals["rcParams"]
    assert rcParams["font.family"] == ["monospace"]
    assert rcParams["figure.facecolor"] == "black"


def _extract_png_dimensions(data_url: str) -> tuple[int, int]:
    """Extract width and height from a PNG data URL."""
    # Remove data URL prefix
    if data_url.startswith("data:image/png;base64,"):
        base64_data = data_url[len("data:image/png;base64,") :]
    else:
        raise ValueError("Not a PNG data URL")

    # Decode base64 to bytes
    png_bytes = base64.b64decode(base64_data)

    # Find IHDR chunk and extract dimensions
    ihdr_index = png_bytes.index(b"IHDR")
    # Next 8 bytes after IHDR are width (4 bytes) and height (4 bytes)
    width, height = struct.unpack(
        ">II", png_bytes[ihdr_index + 4 : ihdr_index + 12]
    )
    return width, height


@pytest.mark.skipif(not HAS_MPL, reason="optional dependencies not installed")
async def test_matplotlib_retina_rendering(
    executing_kernel: Kernel, exec_req: ExecReqProvider
) -> None:
    """Test that matplotlib figures are rendered at 2x DPI for retina displays."""
    from marimo._output.formatters.formatters import register_formatters

    register_formatters(theme="light")

    await executing_kernel.run(
        [
            exec_req.get(
                """
                import matplotlib.pyplot as plt

                # Create a simple figure
                fig, ax = plt.subplots(figsize=(4, 3))
                ax.plot([1, 2, 3], [1, 2, 3])

                # Get the formatted output
                result = fig._mime_()
                """
            )
        ]
    )

    # Get the formatted result from kernel globals
    mime_type, data = executing_kernel.globals["result"]

    # Check that it's a mimebundle
    assert mime_type == "application/vnd.marimo+mimebundle"
    assert isinstance(data, str)

    # Parse the mimebundle
    mimebundle = json.loads(data)
    assert "image/png" in mimebundle

    # Extract PNG data and check dimensions
    png_data_url = mimebundle["image/png"]
    width, height = _extract_png_dimensions(png_data_url)

    # Verify it's rendering at high DPI (should be significantly larger than
    # the base figsize in pixels). At 2x DPI, a 4x3 inch figure should be
    # at least 500x400 pixels (allowing for different base DPI values)
    # The exact value depends on matplotlib's default DPI (can be 72, 90, 100, etc.)
    assert width >= 500, f"Expected high-res width (>500px), got {width}"
    assert height >= 350, f"Expected high-res height (>350px), got {height}"

    # Verify aspect ratio is preserved (4:3 ratio)
    aspect_ratio = width / height
    expected_ratio = 4.0 / 3.0
    assert abs(aspect_ratio - expected_ratio) < 0.1, (
        f"Expected aspect ratio ~{expected_ratio}, got {aspect_ratio}"
    )


@pytest.mark.skipif(not HAS_MPL, reason="optional dependencies not installed")
async def test_matplotlib_retina_metadata(
    executing_kernel: Kernel, exec_req: ExecReqProvider
) -> None:
    """Test that matplotlib figures include proper width/height metadata."""
    from marimo._output.formatters.formatters import register_formatters

    register_formatters(theme="light")

    await executing_kernel.run(
        [
            exec_req.get(
                """
                import matplotlib.pyplot as plt

                # Create a simple figure
                fig, ax = plt.subplots(figsize=(4, 3))
                ax.plot([1, 2, 3], [1, 2, 3])
                result = fig._mime_()
                """
            )
        ]
    )

    # Get the formatted result from kernel globals
    mime_type, data = executing_kernel.globals["result"]
    assert mime_type == "application/vnd.marimo+mimebundle"
    mimebundle_data = json.loads(data)

    # Check for metadata
    assert "__metadata__" in mimebundle_data, (
        "Mimebundle should include metadata"
    )
    metadata = mimebundle_data["__metadata__"]
    assert "image/png" in metadata, (
        "Metadata should include image/png dimensions"
    )

    # Extract actual PNG dimensions
    png_data_url = mimebundle_data["image/png"]
    actual_width, actual_height = _extract_png_dimensions(png_data_url)

    # Metadata dimensions should be half of actual (for retina display)
    png_metadata = metadata["image/png"]
    assert "width" in png_metadata
    assert "height" in png_metadata

    metadata_width = png_metadata["width"]
    metadata_height = png_metadata["height"]

    # Metadata should be approximately half the actual PNG dimensions
    assert abs(metadata_width - actual_width // 2) <= 2, (
        f"Metadata width {metadata_width} should be ~half of actual {actual_width}"
    )
    assert abs(metadata_height - actual_height // 2) <= 2, (
        f"Metadata height {metadata_height} should be ~half of actual {actual_height}"
    )


@pytest.mark.skipif(not HAS_MPL, reason="optional dependencies not installed")
async def test_matplotlib_backwards_compatibility(
    executing_kernel: Kernel, exec_req: ExecReqProvider
) -> None:
    """Test that existing matplotlib code still works with retina rendering."""
    from marimo._output.formatters.formatters import register_formatters

    register_formatters(theme="light")

    # Test various matplotlib output types
    await executing_kernel.run(
        [
            exec_req.get(
                """
                import matplotlib.pyplot as plt
                import numpy as np

                # Test 1: Simple plot
                fig1, ax1 = plt.subplots()
                ax1.plot([1, 2, 3], [1, 2, 3])
                result1 = fig1._mime_()

                # Test 2: Scatter plot
                x = np.random.rand(27)
                y = 20 - np.linspace(2, 20, 27) * x
                fig2, ax2 = plt.subplots()
                ax2.scatter(x, y)
                result2 = fig2._mime_()

                # Test 3: Bar chart
                fig3, ax3 = plt.subplots()
                bars = ax3.bar(['A', 'B', 'C'], [1, 2, 3])
                result3 = fig3._mime_()
                """
            )
        ]
    )

    # Check all outputs were generated successfully
    for result_name in ["result1", "result2", "result3"]:
        mime_type, data = executing_kernel.globals[result_name]
        # Should produce valid output (mimebundle with PNG)
        assert mime_type == "application/vnd.marimo+mimebundle"
        mimebundle = json.loads(data)
        assert "image/png" in mimebundle
