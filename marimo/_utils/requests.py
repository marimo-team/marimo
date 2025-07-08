import http.client
import json
import urllib.parse
from typing import Any, Optional, Union
from urllib.error import HTTPError, URLError

from marimo import __version__

# Utility functions for making HTTP requests,
# without using the requests library or any other external dependencies.

MARIMO_USER_AGENT = f"marimo/{__version__}"


class RequestError(Exception):
    """Exception raised when a request fails."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


class Response:
    """Simple response object similar to requests.Response."""

    def __init__(
        self, status_code: int, content: bytes, headers: dict[str, str]
    ):
        self.status_code = status_code
        self.content = content
        self.headers = headers

    def json(self) -> Any:
        """Parse response content as JSON."""
        return json.loads(self.text())

    def text(self) -> str:
        """Get response content as text."""
        return self.content.decode("utf-8")


def _make_request(
    method: str,
    url: str,
    *,
    params: Optional[dict[str, str]] = None,
    headers: Optional[dict[str, str]] = None,
    data: Optional[Union[dict[str, Any], str]] = None,
    json_data: Optional[dict[str, Any]] = None,
    timeout: Optional[float] = None,
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

    parsed = urllib.parse.urlparse(url)
    path = parsed.path
    if params:
        # Parse existing query parameters
        existing_params = urllib.parse.parse_qs(parsed.query)
        # Flatten existing params (parse_qs returns lists)
        flattened_existing = {k: v[0] for k, v in existing_params.items()}
        # Merge with new params (new params take precedence)
        merged_params = {**flattened_existing, **params}
        query = urllib.parse.urlencode(merged_params)
        path = f"{path}?{query}"
    elif parsed.query:
        # Keep existing query if no new params
        path = f"{path}?{parsed.query}"

    conn = http.client.HTTPSConnection(parsed.netloc, timeout=timeout)

    headers = headers or {}
    if json_data is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(json_data).encode("utf-8")
    elif data is not None:
        if isinstance(data, dict):
            body = urllib.parse.urlencode(data).encode("utf-8")
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        else:
            body = str(data).encode("utf-8")
    else:
        body = None

    try:
        conn.request(method, path, body=body, headers=headers)
        response = conn.getresponse()
        return Response(
            status_code=response.status,
            content=response.read(),
            headers=dict(response.getheaders()),
        )
    except (HTTPError, URLError, ConnectionRefusedError) as e:
        raise RequestError(f"Request failed: to {url}: {str(e)}") from None
    finally:
        conn.close()


def get(
    url: str,
    *,
    params: Optional[dict[str, str]] = None,
    headers: Optional[dict[str, str]] = None,
    timeout: Optional[float] = None,
) -> Response:
    """Make a GET request."""
    return _make_request(
        "GET", url, params=params, headers=headers, timeout=timeout
    )


def post(
    url: str,
    *,
    data: Optional[Union[dict[str, Any], str]] = None,
    json_data: Optional[dict[str, Any]] = None,
    headers: Optional[dict[str, str]] = None,
    timeout: Optional[float] = None,
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
    data: Optional[Union[dict[str, Any], str]] = None,
    json_data: Optional[dict[str, Any]] = None,
    headers: Optional[dict[str, str]] = None,
    timeout: Optional[float] = None,
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
    headers: Optional[dict[str, str]] = None,
    timeout: Optional[float] = None,
) -> Response:
    """Make a DELETE request."""
    return _make_request("DELETE", url, headers=headers, timeout=timeout)
