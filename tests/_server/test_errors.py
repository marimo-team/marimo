from __future__ import annotations

from unittest.mock import MagicMock, patch

import msgspec
from starlette.exceptions import HTTPException
from starlette.requests import Request

from marimo._server.errors import handle_error
from marimo._session.model import SessionMode
from marimo._utils.http import HTTPException as MarimoHTTPException


async def test_http_exception_403_page_request():
    """Page requests should get 401 with WWW-Authenticate header to trigger browser auth"""
    exc = HTTPException(status_code=403)
    # Non-API request (page load)
    request = Request(
        {
            "type": "http",
            "path": "/",
            "headers": [(b"accept", b"text/html")],
        }
    )
    response = await handle_error(request, exc)
    assert response.status_code == 401
    assert response.body == b'{"detail":"Authorization header required"}'
    assert response.headers["WWW-Authenticate"] == "Basic"


async def test_http_exception_403_api_request_by_path():
    """API requests should get 401 without WWW-Authenticate header"""
    exc = HTTPException(status_code=403)
    # API request detected by path
    request = Request(
        {
            "type": "http",
            "path": "/api/kernel/code_autocomplete",
            "headers": [],
        }
    )
    response = await handle_error(request, exc)
    assert response.status_code == 401
    assert response.body == b'{"detail":"Authorization header required"}'
    assert "WWW-Authenticate" not in response.headers


async def test_http_exception_403_api_request_by_accept_header():
    """API requests with Accept: application/json should get 401 without WWW-Authenticate"""
    exc = HTTPException(status_code=403)
    # API request detected by Accept header
    request = Request(
        {
            "type": "http",
            "path": "/some/path",
            "headers": [(b"accept", b"application/json")],
        }
    )
    response = await handle_error(request, exc)
    assert response.status_code == 401
    assert response.body == b'{"detail":"Authorization header required"}'
    assert "WWW-Authenticate" not in response.headers


async def test_http_exception_other():
    # Test other HTTP exceptions
    exc = HTTPException(status_code=404, detail="Not found")
    response = await handle_error(Request({"type": "http"}), exc)
    assert response.status_code == 404
    assert response.body == b'{"detail":"Not found"}'


async def test_marimo_http_exception():
    exc = MarimoHTTPException(status_code=400, detail="Bad request")
    response = await handle_error(Request({"type": "http"}), exc)
    assert response.status_code == 400
    assert response.body == b'{"detail":"Bad request"}'


async def test_module_not_found_error():
    # Mock AppState and session
    mock_app_state = MagicMock()
    mock_app_state.mode = SessionMode.EDIT
    mock_app_state.get_current_session_id.return_value = "test_session"
    mock_app_state.get_current_session.return_value = MagicMock()
    with (
        patch("marimo._server.errors.AppState", return_value=mock_app_state),
        patch(
            "marimo._server.errors.send_message_to_consumer"
        ) as mock_send_message,
    ):
        exc = ModuleNotFoundError(
            "No module named 'missing_package'", name="missing_package"
        )
        response = await handle_error(Request({"type": "http"}), exc)

        assert response.status_code == 500
        assert (
            response.body
            == b'{"detail":"No module named \'missing_package\'"}'
        )
        mock_send_message.assert_called_once()


async def test_not_implemented_error():
    exc = NotImplementedError("Feature not implemented")
    response = await handle_error(Request({"type": "http"}), exc)
    assert response.status_code == 501
    assert response.body == b'{"detail":"Not supported"}'


async def test_type_error():
    exc = TypeError("Invalid type")
    response = await handle_error(Request({"type": "http"}), exc)
    assert response.status_code == 500
    assert response.body == b'{"detail":"Invalid type"}'


async def test_generic_exception():
    exc = Exception("Something went wrong")
    response = await handle_error(Request({"type": "http"}), exc)
    assert response.status_code == 500
    assert response.body == b'{"detail":"Something went wrong"}'


async def test_non_exception_response():
    response = "Not an exception"
    result = await handle_error(Request({"type": "http"}), response)
    assert result == response


async def test_msgspec_validation_error():
    exc = msgspec.ValidationError("Invalid data")
    response = await handle_error(Request({"type": "http"}), exc)
    assert response.status_code == 400
    assert response.body == b'{"detail":"Invalid data"}'
