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
from marimo._runtime.requests import DeleteCellRequest
from marimo._runtime.runtime import Kernel
from tests.conftest import ExecReqProvider


@pytest.mark.skipif(
    not DependencyManager.matplotlib.has(),
    reason="matplotlib is not installed",
)
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
        await k.delete_cell(DeleteCellRequest(cell_id=cell.cell_id))


@pytest.mark.skipif(
    not DependencyManager.matplotlib.has(),
    reason="matplotlib is not installed",
)
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


@pytest.mark.skipif(
    not DependencyManager.matplotlib.has(),
    reason="matplotlib is not installed",
)
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
        mock_request.headers.get.assert_called_once_with("X-Runtime-URL")


def test_get_remote_url_no_request() -> None:
    """Test _get_remote_url when no request exists"""

    with patch("marimo._plugins.stateless.mpl._mpl.app_meta") as mock_app_meta:
        mock_app_meta.return_value.request = None

        result = _get_remote_url()

        assert result == ""


def test_get_remote_url_no_header() -> None:
    """Test _get_remote_url when X-Runtime-URL header is missing"""

    mock_request = MagicMock()
    mock_request.headers.get.return_value = None

    with patch("marimo._plugins.stateless.mpl._mpl.app_meta") as mock_app_meta:
        mock_app_meta.return_value.request = mock_request

        result = _get_remote_url()

        assert result == ""


def test_get_remote_url_empty_header() -> None:
    """Test _get_remote_url when X-Runtime-URL header is empty"""

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
        assert "test_fig" in result
        assert "https://example.com/mpl/8080" in result


def test_template_without_remote_url() -> None:
    """Test _template function without remote URL"""

    with patch("marimo._plugins.stateless.mpl._mpl.app_meta") as mock_app_meta:
        mock_app_meta.return_value.request = None

        result = _template("test_fig", 8080)

        assert "/mpl/8080/ws?figure=test_fig" in result
        assert "test_fig" in result
        assert "/mpl/8080" in result


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
