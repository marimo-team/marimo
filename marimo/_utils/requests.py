import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Optional, Union

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
        self,
        status_code: int,
        content: bytes,
        headers: dict[str, str],
        original_error: Optional[Exception] = None,
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
        """Get response content as text.

        This assumes the response is UTF-8 encoded.
        In future, we can infer the encoding from the headers.
        """
        return self.content.decode("utf-8")

    def raise_for_status(self) -> "Response":
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
        raise RequestError(f"Request failed: {str(e)}") from e


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
