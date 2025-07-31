from typing import Any, Optional, Union
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
    params: Optional[dict[str, str]],
    headers: Optional[dict[str, str]],
    data: Optional[Union[dict[str, Any], str]],
    json_data: Optional[dict[str, Any]],
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
    with patch(
        "urllib.request.urlopen", side_effect=Exception("Network error")
    ):
        with pytest.raises(
            RequestError, match="Request failed: Network error"
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
    url: str, params: Optional[dict[str, str]], expected_url: str
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
