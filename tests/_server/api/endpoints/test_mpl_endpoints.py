# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

from marimo._server.api.endpoints.mpl import figure_endpoints

if TYPE_CHECKING:
    from starlette.testclient import TestClient


class TestMatplotlibProxyEndpoints:
    """Tests for matplotlib proxy endpoints."""

    def setup_method(self) -> None:
        """Clear figure_endpoints before each test."""
        figure_endpoints.clear()

    def teardown_method(self) -> None:
        """Clean up after each test."""
        figure_endpoints.clear()

    @staticmethod
    def test_http_requires_auth(client: TestClient) -> None:
        """Test that HTTP proxy requires authentication."""
        figure_endpoints[1] = "8888"

        # Mock validate_auth to return False (unauthenticated)
        with patch(
            "marimo._server.api.endpoints.mpl.validate_auth", return_value=False
        ):
            response = client.get("/mpl/1/test_path")
            assert response.status_code == 401, response.text
            assert "Unauthorized" in response.text

    @staticmethod
    def test_unauthorized_figure_returns_403(client: TestClient) -> None:
        """Test that accessing unregistered figure returns 403."""
        # Mock auth to pass, but figure not registered
        with patch(
            "marimo._server.api.endpoints.mpl.validate_auth", return_value=True
        ):
            response = client.get("/mpl/999/some_path")
            assert response.status_code == 403, response.text
            assert "Unauthorized" in response.text

    @staticmethod
    def test_connection_error_returns_503(client: TestClient) -> None:
        """Test connection failure returns 503."""
        figure_endpoints[1] = "8888"

        with patch(
            "marimo._server.api.endpoints.mpl.validate_auth", return_value=True
        ):
            with patch("urllib.request.urlopen") as mock_urlopen:
                from urllib.error import URLError

                mock_urlopen.side_effect = URLError("Connection refused")
                response = client.get("/mpl/1/test_path")
                assert response.status_code == 503, response.text
                assert "Matplotlib server is not available" in response.text

    @staticmethod
    def test_successful_proxy(client: TestClient) -> None:
        """Test successful proxying to matplotlib server."""
        figure_endpoints[1] = "8888"

        with patch(
            "marimo._server.api.endpoints.mpl.validate_auth", return_value=True
        ):
            with patch("urllib.request.urlopen") as mock_urlopen:
                mock_response = MagicMock()
                mock_response.status = 200
                mock_response.headers = {"content-type": "text/html"}
                mock_response.read.return_value = b"<html>Success</html>"
                mock_urlopen.return_value.__enter__.return_value = mock_response

                response = client.get("/mpl/1/test")
                assert response.status_code == 200, response.text
                assert response.text == "<html>Success</html>"

    @staticmethod
    def test_query_params_forwarded(client: TestClient) -> None:
        """Test query parameters are forwarded to matplotlib server."""
        figure_endpoints[1] = "8888"

        with patch(
            "marimo._server.api.endpoints.mpl.validate_auth", return_value=True
        ):
            with patch("urllib.request.urlopen") as mock_urlopen:
                mock_response = MagicMock()
                mock_response.status = 200
                mock_response.headers = {}
                mock_response.read.return_value = b""
                mock_urlopen.return_value.__enter__.return_value = mock_response

                client.get("/mpl/1/test?param1=value1&param2=value2")

                request_obj = mock_urlopen.call_args[0][0]
                assert "param1=value1" in request_obj.full_url
                assert "param2=value2" in request_obj.full_url

    @staticmethod
    def test_headers_filtered(client: TestClient) -> None:
        """Test that problematic headers (host, content-length) are filtered."""
        figure_endpoints[1] = "8888"

        with patch(
            "marimo._server.api.endpoints.mpl.validate_auth", return_value=True
        ):
            with patch("urllib.request.urlopen") as mock_urlopen:
                mock_response = MagicMock()
                mock_response.status = 200
                mock_response.headers = {}
                mock_response.read.return_value = b""
                mock_urlopen.return_value.__enter__.return_value = mock_response

                client.get("/mpl/1/test")

                request_obj = mock_urlopen.call_args[0][0]
                assert "Host" not in request_obj.headers
                assert "Content-length" not in request_obj.headers

    @staticmethod
    def test_websocket_requires_auth(client: TestClient) -> None:
        """Test that WebSocket connection requires authentication."""
        from starlette.websockets import WebSocketDisconnect

        # Mock validate_auth to return False (unauthenticated)
        with patch(
            "marimo._server.api.endpoints.mpl.validate_auth", return_value=False
        ):
            try:
                with client.websocket_connect("/mpl/8888/ws"):
                    pass
            except WebSocketDisconnect:
                # Expected - connection should be rejected
                pass

    @staticmethod
    def test_websocket_authenticated_connects(client: TestClient) -> None:
        """Test that authenticated WebSocket connection succeeds."""
        from starlette.websockets import WebSocketDisconnect

        # Mock validate_auth to return True (authenticated)
        with patch(
            "marimo._server.api.endpoints.mpl.validate_auth", return_value=True
        ):
            with patch("websockets.connect") as mock_connect:
                mock_ws = MagicMock()
                mock_context = MagicMock()
                mock_context.__aenter__ = AsyncMock(return_value=mock_ws)
                mock_context.__aexit__ = AsyncMock(return_value=None)
                mock_connect.return_value = mock_context

                async def mock_iter():
                    return
                    yield

                mock_ws.__aiter__ = mock_iter

                try:
                    with client.websocket_connect("/mpl/8888/ws?figure=123"):
                        pass
                except WebSocketDisconnect:
                    pass

                # Verify websockets.connect was called with correct port
                mock_connect.assert_called()
                call_url = mock_connect.call_args[0][0]
                assert "localhost:8888" in call_url
