from __future__ import annotations

import base64
import json

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._runtime.runtime import Kernel
from tests.conftest import ExecReqProvider

HAS_MPL = DependencyManager.matplotlib.has()

pytestmark = pytest.mark.skip(reason="temporarily skipped")


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
    from marimo._output.mpl import _extract_png_dimensions as extract_dims

    if data_url.startswith("data:image/png;base64,"):
        base64_data = data_url[len("data:image/png;base64,") :]
    else:
        raise ValueError("Not a PNG data URL")

    png_bytes = base64.b64decode(base64_data)
    return extract_dims(png_bytes)


@pytest.mark.skipif(not HAS_MPL, reason="optional dependencies not installed")
@pytest.mark.parametrize("dpi", [72, 300])
async def test_matplotlib_image_resolution_respects_dpi(
    executing_kernel: Kernel,
    exec_req: ExecReqProvider,
    dpi: int,
) -> None:
    """Test that the actual image resolution (pixels) scales with DPI."""
    from marimo._output.formatters.formatters import register_formatters

    register_formatters(theme="light")

    await executing_kernel.run(
        [
            exec_req.get(
                f"""
                import matplotlib.pyplot as plt

                # Create an empty figure (no content) to isolate DPI effects
                fig = plt.figure(figsize=(4, 3), dpi={dpi})

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

    # https://matplotlib.org/stable/api/_as_gen/matplotlib.figure.Figure.savefig.html
    pad_inches = 0.1
    calc_width = round((4 + 2 * pad_inches) * dpi)
    calc_height = round((3 + 2 * pad_inches) * dpi)

    assert calc_width - 5 < width < calc_width + 5
    assert calc_height - 5 < height < calc_height + 5

    # Verify aspect ratio is preserved (4:3 ratio)
    aspect_ratio = width / height
    expected_ratio = 4.0 / 3.0
    assert abs(aspect_ratio - expected_ratio) < 0.1, (
        f"Expected aspect ratio ~{expected_ratio}, got {aspect_ratio}"
    )


@pytest.mark.skipif(not HAS_MPL, reason="optional dependencies not installed")
@pytest.mark.parametrize("dpi", [72, 300])
async def test_matplotlib_display_size_remains_constant(
    executing_kernel: Kernel, exec_req: ExecReqProvider, dpi: int
) -> None:
    """Test that the display size in the notebook remains constant even if DPI changes."""
    from marimo._output.formatters.formatters import register_formatters

    register_formatters(theme="light")

    await executing_kernel.run(
        [
            exec_req.get(
                f"""
                import matplotlib.pyplot as plt

                # Create an empty figure (no content) to isolate DPI effects
                fig = plt.figure(figsize=(4, 3), dpi={dpi})
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

    # Metadata dimensions should be figsize (4x3 inches) in 100 DPI.
    png_metadata = metadata["image/png"]
    assert "width" in png_metadata
    assert "height" in png_metadata

    metadata_width = png_metadata["width"]
    metadata_height = png_metadata["height"]

    # https://matplotlib.org/stable/api/_as_gen/matplotlib.figure.Figure.savefig.html
    pad_inches = 0.1
    calc_width = round((4 + 2 * pad_inches) * 100)
    calc_height = round((3 + 2 * pad_inches) * 100)

    assert calc_width - 5 < metadata_width < calc_width + 5
    assert calc_height - 5 < metadata_height < calc_height + 5


@pytest.mark.skipif(not HAS_MPL, reason="optional dependencies not installed")
async def test_matplotlib_backwards_compatibility(
    executing_kernel: Kernel, exec_req: ExecReqProvider
) -> None:
    """Test that existing matplotlib code still works with the new DPI rendering logic."""
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


@pytest.mark.skipif(not HAS_MPL, reason="optional dependencies not installed")
async def test_matplotlib_svg_rendering(
    executing_kernel: Kernel, exec_req: ExecReqProvider
) -> None:
    """Test that matplotlib figures are rendered in SVG format."""
    from marimo._output.formatters.formatters import register_formatters

    register_formatters(theme="light")

    await executing_kernel.run(
        [
            exec_req.get(
                """
                import matplotlib.pyplot as plt

                fmt = plt.rcParams["savefig.format"]
                plt.rcParams["savefig.format"] = "svg"

                # Create a simple figure
                fig, ax = plt.subplots(figsize=(4, 3))
                ax.plot([1, 2, 3], [1, 2, 3])
                result = fig._mime_()

                plt.rcParams["savefig.format"] = fmt
                """
            )
        ]
    )

    # Get the formatted result from kernel globals
    mime_type, data = executing_kernel.globals["result"]

    assert mime_type == "image/svg+xml"
    assert isinstance(data, str)
    assert data.startswith("data:image/svg+xml;base64,PD94")


@pytest.mark.skipif(not HAS_MPL, reason="optional dependencies not installed")
async def test_matplotlib_svg_rendering_in_layout(
    executing_kernel: Kernel, exec_req: ExecReqProvider
) -> None:
    """Test that the SVG output can be used in a layout."""
    from marimo._output.formatters.formatters import register_formatters

    register_formatters(theme="light")

    await executing_kernel.run(
        [
            exec_req.get(
                """
                import marimo as mo
                import matplotlib.pyplot as plt

                fmt = plt.rcParams["savefig.format"]
                plt.rcParams["savefig.format"] = "svg"

                # Create a simple figure
                fig, ax = plt.subplots(figsize=(4, 3))
                ax.plot([1, 2, 3], [1, 2, 3])
                result = mo.hstack([fig])._mime_()

                plt.rcParams["savefig.format"] = fmt
                """
            )
        ]
    )

    # Get the formatted result from kernel globals
    mime_type, data = executing_kernel.globals["result"]

    assert mime_type == "text/html"
    assert isinstance(data, str)
    assert data.startswith("<div")
    assert '<img src="data:image/svg+xml;base64,' in data
