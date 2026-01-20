from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._output.hypertext import Html
from marimo._plugins.stateless.mpl._mpl import (
    _convert_scheme_to_ws,
    _get_remote_url,
    _template,
)
from marimo._runtime.commands import DeleteCellCommand
from marimo._runtime.runtime import Kernel
from tests.conftest import ExecReqProvider

HAS_DEPS = DependencyManager.matplotlib.has()


@pytest.mark.skipif(not HAS_DEPS, reason="matplotlib is not installed")
def test_mpl_interactive_repr_png() -> None:
    """Test that mpl.interactive provides PNG fallback for ipynb export."""
    import base64

    import matplotlib.pyplot as plt

    from marimo._plugins.stateless.mpl._mpl import InteractiveMplHtml

    # Create a simple figure
    fig, ax = plt.subplots()
    ax.plot([1, 2, 3], [1, 2, 3])

    # Create the InteractiveMplHtml object
    html_obj = InteractiveMplHtml("<div>test</div>", fig)

    # Verify _repr_png_ returns valid base64-encoded PNG bytes
    png_b64 = html_obj._repr_png_()
    assert isinstance(png_b64, bytes)

    # Decode and verify it's valid PNG
    png_bytes = base64.b64decode(png_b64)
    assert png_bytes.startswith(b"\x89PNG")  # PNG magic bytes
    assert len(png_bytes) > 100  # Should have substantial content

    plt.close(fig)


@pytest.mark.skipif(not HAS_DEPS, reason="matplotlib is not installed")
def test_mpl_interactive_mime_no_js() -> None:
    """Test that _mime_ returns PNG when in no-JS mode (ipynb export)."""
    import matplotlib.pyplot as plt

    from marimo._output.hypertext import patch_html_for_non_interactive_output
    from marimo._plugins.stateless.mpl._mpl import InteractiveMplHtml

    # Create a simple figure
    fig, ax = plt.subplots()
    ax.plot([1, 2, 3], [1, 2, 3])

    # In normal mode, should return text/html
    html_obj = InteractiveMplHtml("<div>test</div>", fig)
    mimetype, _ = html_obj._mime_()
    assert mimetype == "text/html"

    # In no-JS mode (ipynb export), should return image/png
    with patch_html_for_non_interactive_output():
        html_obj2 = InteractiveMplHtml("<div>test</div>", fig)
        mimetype, data = html_obj2._mime_()
        assert mimetype == "image/png"
        # Data should be the PNG bytes decoded
        assert isinstance(data, str)

    plt.close(fig)


@pytest.mark.skipif(not HAS_DEPS, reason="matplotlib is not installed")
async def test_mpl_interactive(k: Kernel, exec_req: ExecReqProvider) -> None:
    from threading import Thread

    # This tests that the interactive figure is correctly displayed
    # and does not crash when tornado is not installed.

    with patch.object(Thread, "start", lambda self: None):  # noqa: ARG005
        await k.run(
            [
                cell := exec_req.get(
                    """
                    # remove tornado from sys.modules
                    import sys
                    sys.modules.pop("tornado", None)

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
        assert interactive.text.startswith("<iframe srcdoc=")
        await k.delete_cell(DeleteCellCommand(cell_id=cell.cell_id))


@pytest.mark.skipif(not HAS_DEPS, reason="matplotlib is not installed")
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


@pytest.mark.skipif(not HAS_DEPS, reason="matplotlib is not installed")
def test_patch_javascript() -> None:
    from matplotlib.backends.backend_webagg_core import FigureManagerWebAgg

    from marimo._plugins.stateless.mpl._mpl import patch_javascript

    javascript: str = str(FigureManagerWebAgg.get_javascript())  # type: ignore[no-untyped-call]
    assert javascript is not None
    javascript = patch_javascript(javascript)
    assert javascript.count("// canvas.focus();") == 1
    assert javascript.count("// canvas_div.focus();") == 1


def test_get_remote_url_with_request() -> None:
    """Test _get_remote_url when request and headers exist"""

    # Mock the app_meta function and request
    mock_request = MagicMock()
    mock_request.headers.get.return_value = "https://example.com/path/"

    with patch("marimo._plugins.stateless.mpl._mpl.app_meta") as mock_app_meta:
        mock_app_meta.return_value.request = mock_request

        result = _get_remote_url()

        assert result == "https://example.com/path"
        mock_request.headers.get.assert_called_once_with("x-runtime-url")


def test_get_remote_url_no_request() -> None:
    """Test _get_remote_url when no request exists"""

    with patch("marimo._plugins.stateless.mpl._mpl.app_meta") as mock_app_meta:
        mock_app_meta.return_value.request = None

        result = _get_remote_url()

        assert result == ""


def test_get_remote_url_no_header() -> None:
    """Test _get_remote_url when x-runtime-url header is missing"""

    mock_request = MagicMock()
    mock_request.headers.get.return_value = None

    with patch("marimo._plugins.stateless.mpl._mpl.app_meta") as mock_app_meta:
        mock_app_meta.return_value.request = mock_request

        result = _get_remote_url()

        assert result == ""


def test_get_remote_url_empty_header() -> None:
    """Test _get_remote_url when x-runtime-url header is empty"""

    mock_request = MagicMock()
    mock_request.headers.get.return_value = ""

    with patch("marimo._plugins.stateless.mpl._mpl.app_meta") as mock_app_meta:
        mock_app_meta.return_value.request = mock_request

        result = _get_remote_url()

        assert result == ""


def test_convert_scheme_to_ws_http() -> None:
    """Test _convert_scheme_to_ws with http URL"""

    result = _convert_scheme_to_ws("http://example.com/path")
    assert result == "ws://example.com/path"


def test_convert_scheme_to_ws_https() -> None:
    """Test _convert_scheme_to_ws with https URL"""

    result = _convert_scheme_to_ws("https://example.com/path")
    assert result == "wss://example.com/path"


def test_convert_scheme_to_ws_other_scheme() -> None:
    """Test _convert_scheme_to_ws with non-http/https URL"""

    result = _convert_scheme_to_ws("ftp://example.com/path")
    assert result == "ftp://example.com/path"


def test_convert_scheme_to_ws_no_scheme() -> None:
    """Test _convert_scheme_to_ws with URL without scheme"""

    result = _convert_scheme_to_ws("example.com/path")
    assert result == "example.com/path"


def test_template_with_remote_url() -> None:
    """Test _template function with remote URL"""

    mock_request = MagicMock()
    mock_request.headers.get.return_value = "https://example.com"

    with patch("marimo._plugins.stateless.mpl._mpl.app_meta") as mock_app_meta:
        mock_app_meta.return_value.request = mock_request

        result = _template("test_fig", 8080)

        assert "wss://example.com/mpl/8080/ws?figure=test_fig" in result
        assert "://example.com/mpl/test_fig" in result


def test_template_without_remote_url() -> None:
    """Test _template function without remote URL"""

    with patch("marimo._plugins.stateless.mpl._mpl.app_meta") as mock_app_meta:
        mock_app_meta.return_value.request = None

        result = _template("test_fig", 8080)

        assert "/mpl/8080/ws?figure=test_fig" in result
        assert "/mpl/test_fig" in result


def test_template_contains_html_structure() -> None:
    """Test _template function contains proper HTML structure"""

    with patch("marimo._plugins.stateless.mpl._mpl.app_meta") as mock_app_meta:
        mock_app_meta.return_value.request = None

        result = _template("12345", 9000)

        assert "<!DOCTYPE html>" in result
        assert '<html lang="en">' in result
        assert "<head>" in result
        assert "<body>" in result
        assert '<div id="figure"></div>' in result
        assert "12345" in result
        assert "9000" in result


def test_mpl_server_manager() -> None:
    """Test MplServerManager basic functionality"""
    from marimo._plugins.stateless.mpl._mpl import MplServerManager

    manager = MplServerManager()

    # Initially should not be running
    assert not manager.is_running()

    # Mock threading.Thread to avoid actually starting a server
    with patch("threading.Thread") as mock_thread_class:
        mock_thread = MagicMock()
        mock_thread.is_alive.return_value = True
        mock_thread_class.return_value = mock_thread

        # Start should create and return an app
        app = manager.start(app_host="localhost", free_port=12345)

        # Should now be running
        assert manager.is_running()

        # Verify app state
        assert app.state.host == "localhost"
        assert app.state.port == 12345

        # Thread should have been started
        mock_thread.start.assert_called_once()

        # Stop should mark as not running
        manager.stop()
        assert not manager.is_running()


def test_get_or_create_application_with_restart() -> None:
    """Test get_or_create_application handles server restart"""
    from marimo._plugins.stateless.mpl._mpl import (
        _server_manager,
        figure_managers,
        get_or_create_application,
    )

    # Clear any existing state
    globals()["_app"] = None
    figure_managers.figure_managers.clear()

    with patch("threading.Thread") as mock_thread_class:
        # First thread: running
        mock_thread1 = MagicMock()
        mock_thread1.is_alive.return_value = True

        # Second thread: also running (for restart)
        mock_thread2 = MagicMock()
        mock_thread2.is_alive.return_value = True

        mock_thread_class.side_effect = [mock_thread1, mock_thread2]

        # First call should create app
        app1 = get_or_create_application()
        assert app1 is not None
        assert _server_manager.is_running()

        # Simulate server death
        mock_thread1.is_alive.return_value = False

        # Add a figure to test cleanup
        figure_managers.figure_managers["test"] = MagicMock()

        # Next call should restart server and clear figures
        app2 = get_or_create_application()
        assert app2 is not None
        assert app2 is not app1  # Should be a new app instance
        assert (
            len(figure_managers.figure_managers) == 0
        )  # Figures should be cleared

        # Should have started two threads (original + restart)
        assert mock_thread_class.call_count == 2
