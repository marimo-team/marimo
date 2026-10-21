# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import http.client
import json
import urllib.error
import urllib.parse
import urllib.request
from time import monotonic
from typing import Any

from marimo._version import __version__

# Utility functions for making HTTP requests,
# without using the requests library or any other external dependencies.

MARIMO_USER_AGENT = f"marimo/{__version__}"


class RequestError(Exception):
    """Exception raised when a request fails."""

    def __init__(
        self,
        message: str,
        *,
        dispatched: bool | None = None,
        status_code: int | None = None,
    ):
        self.message = message
        self.dispatched = dispatched
        self.status_code = status_code
        super().__init__(self.message)


class Response:
    """Simple response object similar to requests.Response."""

    def __init__(
        self,
        status_code: int,
        content: bytes,
        headers: dict[str, str],
        original_error: Exception | None = None,
    ):
        self.status_code = status_code
        self.content = content
        self.headers = headers
        self.original_error = original_error

    def json(self) -> Any:
        """Parse response content as JSON.

        This assumes the response is UTF-8 encoded.
        In future, we can infer the encoding from the headers.
        """
        return json.loads(self.text())

    def text(self) -> str:
        r"""Get response content as text.

        This assumes the response is UTF-8 encoded.
        In future, we can infer the encoding from the headers.

        Line endings are normalized to Unix style (\n) to match Python's
        text mode behavior when reading files.
        """
        decoded = self.content.decode("utf-8")
        # Normalize line endings: \r\n -> \n, \r -> \n
        # This matches Python's universal newline mode used by Path.read_text()
        return decoded.replace("\r\n", "\n").replace("\r", "\n")

    def raise_for_status(self) -> Response:
        """Raise an exception for non-2xx status codes.

        Returns:
            The response object for chaining.
        """
        if self.status_code >= 300:
            if self.original_error:
                raise self.original_error
            raise RequestError(
                f"Request failed: {self.status_code}. {self.text()}"
            )
        return self


def request(
    method: str,
    url: str,
    *,
    deadline: float,
    max_response_bytes: int,
    data: bytes | None = None,
    headers: dict[str, str] | None = None,
) -> Response:
    """Make one direct HTTP request within a monotonic deadline.

    Redirects, environment proxies, and automatic retries are disabled.
    A failure after dispatch can leave a remote operation's outcome unknown.

    Args:
        method (str): HTTP method.
        url (str): Absolute HTTP or HTTPS URL without credentials or fragments.
        deadline (float): Absolute deadline from `time.monotonic()`.
        max_response_bytes (int): Maximum response body size in bytes.
        data (bytes, optional): Encoded request body.
        headers (dict[str, str], optional): Request headers.

    Raises:
        RequestError: The request fails or exceeds its deadline or size limit.
            `dispatched` indicates whether request transmission started.
            `status_code` contains the HTTP status if headers arrived.
    """
    dispatched = False
    status_code = None

    def failure(message: str) -> RequestError:
        return RequestError(
            message, dispatched=dispatched, status_code=status_code
        )

    def remaining() -> float:
        value = deadline - monotonic()
        if value <= 0:
            raise failure("The request deadline expired")
        return value

    if max_response_bytes < 0:
        raise ValueError("max_response_bytes must be non-negative")
    try:
        endpoint = urllib.parse.urlsplit(url)
        if (
            endpoint.scheme not in {"http", "https"}
            or endpoint.hostname is None
            or endpoint.username is not None
            or endpoint.password is not None
            or endpoint.fragment
        ):
            raise ValueError("Invalid HTTP endpoint")
        connection_type = (
            http.client.HTTPSConnection
            if endpoint.scheme == "https"
            else http.client.HTTPConnection
        )
        connection = connection_type(
            endpoint.hostname, endpoint.port, timeout=remaining()
        )
    except ValueError as error:
        raise failure("Invalid HTTP endpoint") from error

    response: http.client.HTTPResponse | None = None
    try:
        connection.connect()
        connection.auto_open = 0
        transport = connection.sock
        assert transport is not None
        transport.settimeout(remaining())
        path = endpoint.path or "/"
        if endpoint.query:
            path += "?" + endpoint.query
        dispatched = True
        connection.request(method, path, body=data, headers=headers or {})
        transport.settimeout(remaining())
        response = connection.getresponse()
        status_code = response.status
        parts: list[bytes] = []
        size = 0
        while not response.isclosed():
            transport.settimeout(remaining())
            part = response.read1(
                min(64 * 1024, max_response_bytes + 1 - size)
            )
            if not part:
                break
            parts.append(part)
            size += len(part)
            if size > max_response_bytes:
                raise failure("The response body exceeds its size limit")
        if response.length not in (None, 0):
            raise failure("The response body is incomplete")
        remaining()
        return Response(status_code, b"".join(parts), dict(response.headers))
    except (OSError, http.client.HTTPException) as error:
        raise failure("HTTP request failed") from error
    finally:
        if response is not None:
            response.close()
        connection.close()


def _make_request(
    method: str,
    url: str,
    *,
    params: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
    data: dict[str, Any] | str | None = None,
    json_data: dict[str, Any] | None = None,
    timeout: float | None = None,
) -> Response:
    """Make an HTTP request and return a Response object.

    If the URL already contains query parameters and new params are provided,
    they will be merged with new params taking precedence over existing ones.
    """
    assert isinstance(url, str), "url must be a string"
    has_data = data is not None
    has_json_data = json_data is not None
    assert not has_data or not has_json_data, (
        "cannot pass both data and json_data"
    )

    # Handle URL parameters
    if params:
        parsed = urllib.parse.urlparse(url)
        # Parse existing query parameters
        existing_params = urllib.parse.parse_qs(parsed.query)
        # Flatten existing params (parse_qs returns lists)
        flattened_existing = {k: v[0] for k, v in existing_params.items()}
        # Merge with new params (new params take precedence)
        merged_params = {**flattened_existing, **params}
        query = urllib.parse.urlencode(merged_params)
        url = urllib.parse.urlunparse(
            (
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                parsed.params,
                query,
                parsed.fragment,
            )
        )

    # Prepare headers
    request_headers = headers or {}
    if "User-Agent" not in request_headers:
        request_headers["User-Agent"] = MARIMO_USER_AGENT

    # Prepare body
    body = None
    if json_data is not None:
        request_headers["Content-Type"] = "application/json"
        body = json.dumps(json_data).encode("utf-8")
    elif data is not None:
        if isinstance(data, dict):
            body = urllib.parse.urlencode(data).encode("utf-8")
            request_headers["Content-Type"] = (
                "application/x-www-form-urlencoded"
            )
        else:
            body = str(data).encode("utf-8")

    # Create request
    req = urllib.request.Request(
        url, data=body, headers=request_headers, method=method
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return Response(
                status_code=response.getcode(),
                content=response.read(),
                headers=dict(response.headers),
            )
    except urllib.error.HTTPError as e:
        # For HTTP errors, we still want to return a Response object
        return Response(
            status_code=e.code,
            content=e.read(),
            headers=dict(e.headers),
            original_error=e,
        )
    except Exception as e:
        raise RequestError(f"Request failed: {e!s}") from e


def get(
    url: str,
    *,
    params: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float | None = None,
) -> Response:
    """Make a GET request."""
    return _make_request(
        "GET", url, params=params, headers=headers, timeout=timeout
    )


def post(
    url: str,
    *,
    data: dict[str, Any] | str | None = None,
    json_data: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float | None = None,
) -> Response:
    """Make a POST request."""
    return _make_request(
        "POST",
        url,
        data=data,
        json_data=json_data,
        headers=headers,
        timeout=timeout,
    )


def put(
    url: str,
    *,
    data: dict[str, Any] | str | None = None,
    json_data: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float | None = None,
) -> Response:
    """Make a PUT request."""
    return _make_request(
        "PUT",
        url,
        data=data,
        json_data=json_data,
        headers=headers,
        timeout=timeout,
    )


def delete(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: float | None = None,
) -> Response:
    """Make a DELETE request."""
    return _make_request("DELETE", url, headers=headers, timeout=timeout)
