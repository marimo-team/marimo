from __future__ import annotations

from unittest.mock import MagicMock, patch

import msgspec
import pytest
from starlette.exceptions import HTTPException
from starlette.requests import Request

from marimo._dependencies.errors import ManyModulesNotFoundError
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


async def test_many_modules_not_found_error_in_edit_mode():
    """Test ManyModulesNotFoundError sends package alert for multiple packages"""
    mock_app_state = MagicMock()
    mock_app_state.mode = SessionMode.EDIT
    mock_app_state.get_current_session_id.return_value = "test_session"
    mock_session = MagicMock()
    mock_app_state.get_current_session.return_value = mock_session

    with (
        patch("marimo._server.errors.AppState", return_value=mock_app_state),
        patch(
            "marimo._server.errors.send_message_to_consumer"
        ) as mock_send_message,
        patch("marimo._server.errors.is_python_isolated", return_value=False),
    ):
        exc = ManyModulesNotFoundError(
            ["numpy", "pandas", "scipy"],
            "No modules named: numpy, pandas, scipy",
        )
        response = await handle_error(Request({"type": "http"}), exc)

        assert response.status_code == 500
        mock_send_message.assert_called_once()
        # Verify the notification contains all package names
        call_args = mock_send_message.call_args
        notification = call_args.kwargs["operation"]
        assert notification.packages == ["numpy", "pandas", "scipy"]
        assert notification.isolated is False


async def test_module_not_found_error_without_name():
    """Test ModuleNotFoundError without name attribute returns 500 without alert"""
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
        # ModuleNotFoundError without name attribute
        exc = ModuleNotFoundError("No module named 'something'")
        exc.name = None
        response = await handle_error(Request({"type": "http"}), exc)

        assert response.status_code == 500
        # Should not send package alert
        mock_send_message.assert_not_called()


async def test_module_not_found_error_in_run_mode():
    """Test ModuleNotFoundError in RUN mode doesn't send package alert"""
    mock_app_state = MagicMock()
    mock_app_state.mode = SessionMode.RUN
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
        # Should not send alert in RUN mode
        mock_send_message.assert_not_called()


async def test_module_not_found_error_without_session():
    """Test ModuleNotFoundError without active session"""
    mock_app_state = MagicMock()
    mock_app_state.mode = SessionMode.EDIT
    mock_app_state.get_current_session_id.return_value = None
    mock_app_state.get_current_session.return_value = None

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
        # Should not send alert without session
        mock_send_message.assert_not_called()


async def test_module_not_found_error_alert_failure():
    """Test that error in sending package alert is handled gracefully"""
    mock_app_state = MagicMock()
    mock_app_state.mode = SessionMode.EDIT
    mock_app_state.get_current_session_id.return_value = "test_session"
    mock_app_state.get_current_session.return_value = MagicMock()

    with (
        patch("marimo._server.errors.AppState", return_value=mock_app_state),
        patch(
            "marimo._server.errors.send_message_to_consumer",
            side_effect=Exception("Failed to send"),
        ),
        patch("marimo._server.errors.LOGGER") as mock_logger,
    ):
        exc = ModuleNotFoundError(
            "No module named 'missing_package'", name="missing_package"
        )
        # Should not raise, but log the error
        response = await handle_error(Request({"type": "http"}), exc)

        assert response.status_code == 500
        mock_logger.warning.assert_called()


async def test_marimo_http_exception_server_error_logs():
    """Test that server errors (5xx) from MarimoHTTPException are logged"""
    with patch("marimo._server.errors.LOGGER") as mock_logger:
        exc = MarimoHTTPException(status_code=500, detail="Internal error")
        response = await handle_error(Request({"type": "http"}), exc)

        assert response.status_code == 500
        assert response.body == b'{"detail":"Internal error"}'
        mock_logger.error.assert_called_once()


async def test_marimo_http_exception_client_error_no_logs():
    """Test that client errors (4xx) from MarimoHTTPException are not logged"""
    with patch("marimo._server.errors.LOGGER") as mock_logger:
        exc = MarimoHTTPException(status_code=400, detail="Bad request")
        response = await handle_error(Request({"type": "http"}), exc)

        assert response.status_code == 400
        assert response.body == b'{"detail":"Bad request"}'
        mock_logger.error.assert_not_called()


async def test_http_exception_with_custom_headers():
    """Test HTTPException preserves custom headers"""
    exc = HTTPException(
        status_code=429,
        detail="Rate limited",
        headers={"Retry-After": "60", "X-Custom": "value"},
    )
    response = await handle_error(Request({"type": "http"}), exc)

    assert response.status_code == 429
    assert response.body == b'{"detail":"Rate limited"}'
    assert response.headers["Retry-After"] == "60"
    assert response.headers["X-Custom"] == "value"


async def test_accept_header_case_insensitive():
    """Test that Accept header check is case-insensitive"""
    exc = HTTPException(status_code=403)
    # Mixed case Accept header
    request = Request(
        {
            "type": "http",
            "path": "/some/path",
            "headers": [(b"accept", b"Application/JSON")],
        }
    )
    response = await handle_error(request, exc)
    assert response.status_code == 401
    assert "WWW-Authenticate" not in response.headers


async def test_accept_header_with_multiple_types():
    """Test Accept header with multiple content types including JSON"""
    exc = HTTPException(status_code=403)
    request = Request(
        {
            "type": "http",
            "path": "/some/path",
            "headers": [
                (b"accept", b"text/html,application/json,application/xml")
            ],
        }
    )
    response = await handle_error(request, exc)
    assert response.status_code == 401
    # Should be treated as API request
    assert "WWW-Authenticate" not in response.headers


async def test_module_not_found_with_isolated_environment():
    """Test ModuleNotFoundError in isolated Python environment"""
    mock_app_state = MagicMock()
    mock_app_state.mode = SessionMode.EDIT
    mock_app_state.get_current_session_id.return_value = "test_session"
    mock_app_state.get_current_session.return_value = MagicMock()

    with (
        patch("marimo._server.errors.AppState", return_value=mock_app_state),
        patch(
            "marimo._server.errors.send_message_to_consumer"
        ) as mock_send_message,
        patch("marimo._server.errors.is_python_isolated", return_value=True),
    ):
        exc = ModuleNotFoundError(
            "No module named 'missing_package'", name="missing_package"
        )
        response = await handle_error(Request({"type": "http"}), exc)

        assert response.status_code == 500
        mock_send_message.assert_called_once()
        # Verify isolated flag is set
        call_args = mock_send_message.call_args
        notification = call_args.kwargs["operation"]
        assert notification.isolated is True


@pytest.mark.parametrize(
    ("status_code", "detail"),
    [
        (400, "Bad Request"),
        (401, "Unauthorized"),
        (404, "Not Found"),
        (500, "Internal Server Error"),
        (502, "Bad Gateway"),
        (503, "Service Unavailable"),
    ],
)
async def test_http_exception_various_status_codes(
    status_code: int, detail: str
):
    """Test handle_error with various HTTP status codes (except 403)"""
    exc = HTTPException(status_code=status_code, detail=detail)
    response = await handle_error(Request({"type": "http"}), exc)

    assert response.status_code == status_code
    assert response.body == f'{{"detail":"{detail}"}}'.encode()


async def test_appstate_initialization_failure():
    """Test graceful handling when AppState initialization fails"""
    with patch(
        "marimo._server.errors.AppState", side_effect=Exception("Init failed")
    ):
        exc = ModuleNotFoundError(
            "No module named 'missing_package'", name="missing_package"
        )
        # Should still return 500 even if AppState fails
        response = await handle_error(Request({"type": "http"}), exc)
        assert response.status_code == 500
