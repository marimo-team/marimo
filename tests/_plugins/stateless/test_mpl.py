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
    import base64

    import matplotlib.pyplot as plt

    from marimo._plugins.stateless.mpl._mpl import NonInteractiveMplHtml

    fig, ax = plt.subplots()
    ax.plot([1, 2, 3], [1, 2, 3])

    html = NonInteractiveMplHtml(fig)
    mime_type, data = html._mime_()
    assert mime_type == "image/png"
    assert data.startswith("data:image/png;base64,")

    # Decode the base64 payload and verify it's a valid PNG.
    b64_payload = data.split(",", 1)[1]
    raw_png = base64.b64decode(b64_payload)
    assert raw_png.startswith(b"\x89PNG")

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


@pytest.mark.requires("matplotlib")
def test_mpl_interactive_subfigure_falls_back_to_png() -> None:
    """SubFigure cannot be attached to a WebAgg canvas (matplotlib limitation),
    so mo.mpl.interactive should fall back to a static PNG and warn.
    """
    import warnings

    import matplotlib.pyplot as plt

    from marimo._plugins.stateless.mpl._mpl import (
        NonInteractiveMplHtml,
        interactive,
    )
    from marimo._runtime.context.kernel_context import KernelRuntimeContext

    parent = plt.figure(figsize=(8, 4), dpi=100)
    sub_left, _sub_right = parent.subfigures(1, 2)
    sub_left.subplots().plot([1, 2, 3])

    mock_ctx = MagicMock(spec=KernelRuntimeContext)
    mock_ctx.virtual_files_supported = True

    with (
        patch(
            "marimo._plugins.stateless.mpl._mpl.get_context",
            return_value=mock_ctx,
        ),
        warnings.catch_warnings(record=True) as captured,
    ):
        warnings.simplefilter("always")
        result = interactive(sub_left)

    assert isinstance(result, NonInteractiveMplHtml)

    # A UserWarning explaining the fallback should have been emitted.
    subfigure_warnings = [w for w in captured if "SubFigure" in str(w.message)]
    assert len(subfigure_warnings) == 1
    assert issubclass(subfigure_warnings[0].category, UserWarning)

    plt.close(parent)


@pytest.mark.requires("matplotlib")
def test_new_figure_manager_suppresses_thread_warning() -> None:
    """Regression test for https://github.com/marimo-team/marimo/issues/8747.

    new_figure_manager_given_figure should not emit the
    'Starting a Matplotlib GUI outside of the main thread' warning
    because WebAgg only uses software rendering.
    """
    import threading
    import warnings

    import matplotlib.pyplot as plt

    from marimo._plugins.stateless.mpl._mpl import (
        new_figure_manager_given_figure,
    )

    fig, ax = plt.subplots()
    ax.plot([1, 2, 3])

    captured: list[warnings.WarningMessage] = []

    manager = None

    def run_in_thread() -> None:
        nonlocal manager
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            manager = new_figure_manager_given_figure(id(fig), fig)
            captured.extend(w)

    t = threading.Thread(target=run_in_thread)
    t.start()
    t.join()

    thread_warnings = [
        w for w in captured if "outside of the main thread" in str(w.message)
    ]
    assert thread_warnings == [], (
        f"Expected no thread warning, got: {thread_warnings}"
    )

    plt.close(fig)
