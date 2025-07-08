from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from marimo._utils.requests import (
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
    mock_response.status = 200
    mock_response.read.return_value = b'{"key": "value"}'
    mock_response.getheaders.return_value = [
        ("Content-Type", "application/json")
    ]

    mock_conn = MagicMock()
    mock_conn.getresponse.return_value = mock_response

    with patch("http.client.HTTPSConnection", return_value=mock_conn):
        response = _make_request(
            method,
            url,
            params=params,
            headers=headers,
            data=data,
            json_data=json_data,
        )

        # Verify connection was made with correct parameters
        mock_conn.request.assert_called_once()
        call_args = mock_conn.request.call_args[0]
        call_kwargs = mock_conn.request.call_args[1]

        assert call_args[0] == method
        if params:
            assert "param=value" in call_args[1]
        assert call_kwargs["body"] == expected_body

        # Verify headers
        actual_headers = call_kwargs["headers"]
        if headers:
            actual_headers.update(headers)
        if expected_headers:
            for key, value in expected_headers.items():
                assert actual_headers[key] == value

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


@pytest.mark.parametrize(
    ("url", "params", "expected_path"),
    [
        # URL with no existing params, add new params
        ("https://api.example.com", {"new": "value"}, "/path?new=value"),
        # URL with existing params, add new params (merge)
        (
            "https://api.example.com?existing=param",
            {"new": "value"},
            "/path?existing=param&new=value",
        ),
        # URL with existing params, no new params (preserve existing)
        (
            "https://api.example.com?existing=param",
            None,
            "/path?existing=param",
        ),
        # URL with no params at all
        ("https://api.example.com", None, "/path"),
        # URL with existing params, new params override existing
        (
            "https://api.example.com?key=old",
            {"key": "new"},
            "/path?key=new",
        ),
        # URL with multiple existing params, add new params
        (
            "https://api.example.com?a=1&b=2",
            {"c": "3"},
            "/path?a=1&b=2&c=3",
        ),
        # URL with multiple existing params, override some
        (
            "https://api.example.com?a=1&b=2",
            {"b": "new", "c": "3"},
            "/path?a=1&b=new&c=3",
        ),
    ],
)
def test_url_parameter_handling(
    url: str, params: dict[str, str] | None, expected_path: str
):
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.read.return_value = b'{"success": true}'
    mock_response.getheaders.return_value = [
        ("Content-Type", "application/json")
    ]

    mock_conn = MagicMock()
    mock_conn.getresponse.return_value = mock_response

    with patch("http.client.HTTPSConnection", return_value=mock_conn):
        # Replace the actual URL with a test URL that has /path
        test_url = url.replace("api.example.com", "api.example.com/path")
        _make_request("GET", test_url, params=params)

        # Verify the path was constructed correctly
        call_args = mock_conn.request.call_args[0]
        actual_path = call_args[1]

        # Parse both paths to compare query parameters regardless of order
        from urllib.parse import parse_qs, urlparse

        actual_parsed = urlparse(actual_path)
        expected_parsed = urlparse(expected_path)

        assert actual_parsed.path == expected_parsed.path
        if expected_parsed.query:
            actual_query = parse_qs(actual_parsed.query)
            expected_query = parse_qs(expected_parsed.query)
            assert actual_query == expected_query
        else:
            assert actual_parsed.query == ""
