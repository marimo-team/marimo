from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from marimo._output.hypertext import Html
from marimo._runtime.commands import DeleteCellCommand
from marimo._runtime.runtime import Kernel
from tests.conftest import ExecReqProvider


@pytest.mark.requires("matplotlib")
def test_mpl_interactive_repr_png() -> None:
    """Test that mpl_interactive provides PNG fallback for ipynb export."""
    import base64

    import matplotlib.pyplot as plt

    from marimo._plugins.stateless.mpl._mpl import png_bytes

    # Create a simple figure
    fig, ax = plt.subplots()
    ax.plot([1, 2, 3], [1, 2, 3])

    # Verify png_bytes returns valid base64-encoded PNG bytes
    png_b64 = png_bytes(fig)
    assert isinstance(png_b64, bytes)

    # Decode and verify it's valid PNG
    raw_png = base64.b64decode(png_b64)
    assert raw_png.startswith(b"\x89PNG")  # PNG magic bytes
    assert len(raw_png) > 100  # Should have substantial content

    plt.close(fig)


@pytest.mark.requires("matplotlib")
async def test_mpl_interactive(k: Kernel, exec_req: ExecReqProvider) -> None:
    # This tests that the interactive figure is correctly created
    # as a UIElement and does not crash.
    await k.run(
        [
            cell := exec_req.get(
                """
                import marimo as mo
                import matplotlib.pyplot as plt
                plt.plot([1, 2])
                try:
                    interactive = mo.mpl.interactive(plt.gcf())
                except Exception as e:
                    interactive = str(e)
                """
            ),
        ]
    )

    interactive = k.globals["interactive"]
    assert isinstance(interactive, Html)
    # Should contain the marimo-mpl-interactive component
    assert "marimo-mpl-interactive" in interactive.text
    await k.delete_cell(DeleteCellCommand(cell_id=cell.cell_id))


@pytest.mark.requires("matplotlib")
async def test_mpl_show(k: Kernel, exec_req: ExecReqProvider) -> None:
    await k.run(
        [
            exec_req.get(
                """
                import matplotlib.pyplot as plt
                plt.plot([1, 2])
                plt.show()
                """
            )
        ]
    )


@pytest.mark.requires("matplotlib")
def test_patch_javascript() -> None:
    from matplotlib.backends.backend_webagg_core import FigureManagerWebAgg

    from marimo._plugins.stateless.mpl._mpl import patch_javascript

    javascript: str = str(FigureManagerWebAgg.get_javascript())  # type: ignore[no-untyped-call]
    assert javascript is not None
    javascript = patch_javascript(javascript)
    assert javascript.count("// canvas.focus();") == 1
    assert javascript.count("// canvas_div.focus();") == 1


@pytest.mark.requires("matplotlib")
def test_non_interactive_mpl_mime_returns_data_uri() -> None:
    """Test that NonInteractiveMplHtml._mime_ returns a data URI."""
    import matplotlib.pyplot as plt

    from marimo._plugins.stateless.mpl._mpl import NonInteractiveMplHtml

    fig, ax = plt.subplots()
    ax.plot([1, 2, 3], [1, 2, 3])

    html = NonInteractiveMplHtml(fig)
    mime_type, data = html._mime_()
    assert mime_type == "image/png"
    assert data.startswith("data:image/png;base64,")

    plt.close(fig)


@pytest.mark.requires("matplotlib")
def test_mpl_interactive_fallback_when_virtual_files_not_supported() -> None:
    """Test that mpl.interactive falls back to PNG when virtual_files_supported=False."""
    import matplotlib.pyplot as plt

    from marimo._plugins.stateless.mpl._mpl import interactive
    from marimo._runtime.context.kernel_context import KernelRuntimeContext

    # Create a simple figure
    fig, ax = plt.subplots()
    ax.plot([1, 2, 3], [1, 2, 3])

    # Mock the context to have virtual_files_supported=False (simulating HTML export)
    mock_ctx = MagicMock(spec=KernelRuntimeContext)
    mock_ctx.virtual_files_supported = False

    with patch(
        "marimo._plugins.stateless.mpl._mpl.get_context", return_value=mock_ctx
    ):
        # Call interactive - should fallback to static PNG
        result = interactive(fig)

        # Should return Html object
        assert isinstance(result, Html)
        # Should NOT contain the interactive plugin
        assert "marimo-mpl-interactive" not in result.text
        # Should contain a PNG mimetype
        assert result._mime_()[0] == "image/png"

    plt.close(fig)
