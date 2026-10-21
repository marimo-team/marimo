import socket
import time
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from marimo._utils.requests import (
    RequestError,
    Response,
    _make_request,
    delete,
    get,
    post,
    put,
    request,
)


def test_response_object():
    response = Response(
        200, b'{"key": "value"}', {"Content-Type": "application/json"}
    )
    assert response.status_code == 200
    assert response.content == b'{"key": "value"}'
    assert response.headers == {"Content-Type": "application/json"}
    assert response.text() == '{"key": "value"}'
    assert response.json() == {"key": "value"}


def test_response_raise_for_status():
    # Test that raise_for_status does not raise for success codes
    success_response = Response(200, b"OK", {})
    success_response.raise_for_status()  # Should not raise
    assert success_response is success_response.raise_for_status()

    # Test that raise_for_status raises for error codes
    error_response = Response(404, b"Not Found", {})
    with pytest.raises(RequestError, match="Request failed: 404"):
        error_response.raise_for_status()

    # Test various error codes
    for status_code in [300, 400, 401, 403, 404, 500, 502, 503]:
        error_response = Response(status_code, b"Error", {})
        with pytest.raises(
            RequestError, match=f"Request failed: {status_code}"
        ):
            error_response.raise_for_status()

    # Test that success codes (2xx) don't raise
    for status_code in [200, 201, 202, 204]:
        success_response = Response(status_code, b"Success", {})
        success_response.raise_for_status()  # Should not raise


@pytest.mark.parametrize(
    (
        "method",
        "url",
        "params",
        "headers",
        "data",
        "json_data",
        "expected_body",
        "expected_headers",
    ),
    [
        # GET request
        (
            "GET",
            "https://api.example.com",
            {"param": "value"},
            {"Authorization": "Bearer token"},
            None,
            None,
            None,
            {"Authorization": "Bearer token"},
        ),
        # POST with form data
        (
            "POST",
            "https://api.example.com",
            None,
            None,
            {"key": "value"},
            None,
            b"key=value",
            {"Content-Type": "application/x-www-form-urlencoded"},
        ),
        # POST with JSON data
        (
            "POST",
            "https://api.example.com",
            None,
            None,
            None,
            {"key": "value"},
            b'{"key": "value"}',
            {"Content-Type": "application/json"},
        ),
        # POST with string data
        (
            "POST",
            "https://api.example.com",
            None,
            None,
            "raw data",
            None,
            b"raw data",
            {},
        ),
    ],
)
def test_make_request(
    method: str,
    url: str,
    params: dict[str, str] | None,
    headers: dict[str, str] | None,
    data: dict[str, Any] | str | None,
    json_data: dict[str, Any] | None,
    expected_body: bytes,
    expected_headers: dict[str, str],
):
    mock_response = MagicMock()
    mock_response.getcode.return_value = 200
    mock_response.read.return_value = b'{"key": "value"}'
    mock_response.headers = {"Content-Type": "application/json"}
    mock_response.__enter__.return_value = mock_response
    mock_response.__exit__.return_value = None

    with patch(
        "urllib.request.urlopen", return_value=mock_response
    ) as mock_urlopen:
        response = _make_request(
            method,
            url,
            params=params,
            headers=headers,
            data=data,
            json_data=json_data,
        )

        # Verify request was made
        mock_urlopen.assert_called_once()
        request_arg = mock_urlopen.call_args[0][0]

        # Check method and URL
        assert request_arg.get_method() == method
        if params:
            assert "param=value" in request_arg.full_url

        # Check body
        assert request_arg.data == expected_body

        # Check headers
        for key, value in expected_headers.items():
            # urllib.request.Request normalizes header names to Title-case
            # We need to check the actual header values as they're stored
            found_header = False
            for header_name, header_value in request_arg.headers.items():
                if header_name.lower() == key.lower():
                    assert header_value == value
                    found_header = True
                    break
            assert found_header, f"Header {key} not found in request headers"

        # Verify response
        assert response.status_code == 200
        assert response.content == b'{"key": "value"}'
        assert response.headers == {"Content-Type": "application/json"}


def test_invalid_url():
    with pytest.raises(AssertionError, match="url must be a string"):
        _make_request("GET", 123)  # type: ignore


def test_conflicting_data_and_json():
    with pytest.raises(
        AssertionError, match="cannot pass both data and json_data"
    ):
        _make_request(
            "POST",
            "https://api.example.com",
            data={"key": "value"},
            json_data={"key": "value"},
        )


def test_http_methods():
    with patch("marimo._utils.requests._make_request") as mock_make_request:
        # Test GET
        get("https://api.example.com", params={"key": "value"})
        mock_make_request.assert_called_with(
            "GET",
            "https://api.example.com",
            params={"key": "value"},
            headers=None,
            timeout=None,
        )

        # Test POST
        post("https://api.example.com", json_data={"key": "value"})
        mock_make_request.assert_called_with(
            "POST",
            "https://api.example.com",
            data=None,
            json_data={"key": "value"},
            headers=None,
            timeout=None,
        )

        # Test PUT
        put("https://api.example.com", data={"key": "value"})
        mock_make_request.assert_called_with(
            "PUT",
            "https://api.example.com",
            data={"key": "value"},
            json_data=None,
            headers=None,
            timeout=None,
        )

        # Test DELETE
        delete("https://api.example.com")
        mock_make_request.assert_called_with(
            "DELETE", "https://api.example.com", headers=None, timeout=None
        )


def test_http_error_handling():
    """Test that HTTP errors return Response objects instead of raising exceptions."""
    import urllib.error

    # Mock an HTTP error
    mock_fp = MagicMock()
    mock_fp.read.return_value = b'{"error": "not found"}'

    mock_error = urllib.error.HTTPError(
        url="https://api.example.com",
        code=404,
        msg="Not Found",
        hdrs={"Content-Type": "application/json"},
        fp=mock_fp,
    )

    with patch("urllib.request.urlopen", side_effect=mock_error):
        response = _make_request("GET", "https://api.example.com")

        assert response.status_code == 404
        assert response.content == b'{"error": "not found"}'
        assert response.headers == {"Content-Type": "application/json"}


def test_request_error_handling():
    """Test that other exceptions are converted to RequestError."""
    with (
        patch(
            "urllib.request.urlopen", side_effect=Exception("Network error")
        ),
        pytest.raises(RequestError, match="Request failed: Network error"),
    ):
        _make_request("GET", "https://api.example.com")


@pytest.mark.parametrize(
    ("url", "params", "expected_url"),
    [
        # URL with no existing params, add new params
        (
            "https://api.example.com/path",
            {"new": "value"},
            "https://api.example.com/path?new=value",
        ),
        # URL with existing params, add new params (merge)
        (
            "https://api.example.com/path?existing=param",
            {"new": "value"},
            "https://api.example.com/path?existing=param&new=value",
        ),
        # URL with existing params, no new params (preserve existing)
        (
            "https://api.example.com/path?existing=param",
            None,
            "https://api.example.com/path?existing=param",
        ),
        # URL with no params at all
        ("https://api.example.com/path", None, "https://api.example.com/path"),
        # URL with existing params, new params override existing
        (
            "https://api.example.com/path?key=old",
            {"key": "new"},
            "https://api.example.com/path?key=new",
        ),
        # URL with multiple existing params, add new params
        (
            "https://api.example.com/path?a=1&b=2",
            {"c": "3"},
            "https://api.example.com/path?a=1&b=2&c=3",
        ),
        # URL with multiple existing params, override some
        (
            "https://api.example.com/path?a=1&b=2",
            {"b": "new", "c": "3"},
            "https://api.example.com/path?a=1&b=new&c=3",
        ),
    ],
)
def test_url_parameter_handling(
    url: str, params: dict[str, str] | None, expected_url: str
):
    mock_response = MagicMock()
    mock_response.getcode.return_value = 200
    mock_response.read.return_value = b'{"key": "value"}'
    mock_response.headers = {"Content-Type": "application/json"}
    mock_response.__enter__.return_value = mock_response
    mock_response.__exit__.return_value = None

    with patch(
        "urllib.request.urlopen", return_value=mock_response
    ) as mock_urlopen:
        _make_request("GET", url, params=params)

        # Verify the URL was constructed correctly
        request_arg = mock_urlopen.call_args[0][0]
        assert request_arg.full_url == expected_url


@pytest.fixture
def endpoint(http_endpoint):
    http_endpoint.headers["Location"] = "/redirect-target"
    return http_endpoint.url, http_endpoint


@pytest.mark.parametrize("status", [200, 302, 307, 400, 403, 503])
def test_direct_request_does_not_follow_redirects_or_use_proxies(
    endpoint, monkeypatch, status
):
    url, state = endpoint
    state.status = status
    monkeypatch.setenv("http_proxy", "http://127.0.0.1:1")
    monkeypatch.setenv("no_proxy", "")
    response = request(
        "POST",
        url + "/message?target=one",
        data=b"payload",
        headers={"Authorization": "Bearer private-token"},
        deadline=time.monotonic() + 1,
        max_response_bytes=len(state.body),
    )
    assert response.status_code == status
    assert response.content == state.body
    assert response.headers["Location"] == "/redirect-target"
    assert [
        (r.method, r.path, r.headers.get("Authorization"), r.body)
        for r in state.requests
    ] == [("POST", "/message?target=one", "Bearer private-token", b"payload")]


def test_direct_request_limits_response_bytes(endpoint):
    url, state = endpoint
    with pytest.raises(RequestError, match="size limit") as error:
        request(
            "GET", url, deadline=time.monotonic() + 1, max_response_bytes=2
        )
    assert error.value.dispatched is True
    assert error.value.status_code == 200
    assert len(state.requests) == 1


def test_direct_request_rejects_truncated_body(endpoint):
    url, state = endpoint
    state.content_length = len(state.body) + 10
    with pytest.raises(RequestError, match="incomplete") as error:
        request(
            "GET", url, deadline=time.monotonic() + 1, max_response_bytes=100
        )
    assert error.value.dispatched is True
    assert error.value.status_code == 200
    assert len(state.requests) == 1


def test_direct_request_uses_one_deadline_for_streamed_body(endpoint):
    url, state = endpoint
    state.chunk_delay = 0.04
    started = time.monotonic()
    with pytest.raises(RequestError) as error:
        request("GET", url, deadline=started + 0.1, max_response_bytes=100)
    assert time.monotonic() - started < 0.25
    assert error.value.dispatched is True
    assert error.value.status_code == 200
    assert len(state.requests) == 1


def test_direct_request_expired_deadline_prevents_dispatch(endpoint):
    url, state = endpoint
    with pytest.raises(RequestError, match="deadline") as error:
        request(
            "POST", url, deadline=time.monotonic() - 1, max_response_bytes=100
        )
    assert error.value.dispatched is False
    assert error.value.status_code is None
    assert state.requests == []


def test_direct_request_connection_failure_precedes_dispatch():
    with socket.socket() as closed:
        closed.bind(("127.0.0.1", 0))
        port = closed.getsockname()[1]
        with pytest.raises(RequestError) as error:
            request(
                "POST",
                f"http://127.0.0.1:{port}",
                deadline=time.monotonic() + 1,
                max_response_bytes=100,
            )
    assert error.value.dispatched is False
    assert error.value.status_code is None


@pytest.mark.parametrize(
    "url",
    [
        "file:///tmp/message",
        "http:///message",
        "http://private-token@localhost/message",
        "http://localhost/message#fragment",
        "http://localhost:invalid/message",
    ],
)
def test_direct_request_rejects_invalid_endpoints_before_dispatch(url):
    with pytest.raises(RequestError, match="Invalid HTTP endpoint") as error:
        request(
            "POST", url, deadline=time.monotonic() + 1, max_response_bytes=100
        )
    assert error.value.dispatched is False
    assert error.value.status_code is None
