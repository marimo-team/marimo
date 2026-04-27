from __future__ import annotations

from collections import defaultdict
from typing import Any

import msgspec
from starlette.authentication import SimpleUser
from starlette.datastructures import URL, Headers, QueryParams
from starlette.requests import HTTPConnection

from marimo._runtime.commands import HTTPRequest


class MockHTTPConnection(HTTPConnection):
    def __init__(
        self,
        url: str = "http://localhost:8000/test?param1=value1&param2=value2",
        headers: dict[str, str] | None = None,
        path_params: dict[str, Any] | None = None,
        user: Any = None,
    ):
        url_obj = URL(url)
        # Convert headers to list of tuples as expected by Starlette
        raw_headers = [(k.lower(), v) for k, v in (headers or {}).items()]
        scope: dict[str, Any] = {
            "type": "http",
            "method": "GET",
            "headers": dict(raw_headers),
            "path": url_obj.path,
            "path_params": path_params or {},
        }
        if user is not None:
            scope["user"] = user
        super().__init__(scope)
        self._url = url_obj
        self._base_url = URL("http://localhost:8000")

    @property
    def url(self) -> URL:
        return self._url

    @property
    def base_url(self) -> URL:
        return self._base_url

    @property
    def query_params(self) -> QueryParams:
        return QueryParams(self.url.query)

    @property
    def headers(self) -> Headers:
        return Headers(headers=self.scope["headers"])


def test_http_request_like_basic_mapping():
    request = HTTPRequest(
        url={"path": "/test"},
        base_url={"path": "/"},
        headers={"Content-Type": "application/json"},
        query_params=defaultdict(list),
        path_params={},
        cookies={},
        user={"is_authenticated": True},
        meta={},
    )

    assert request["url"] == {"path": "/test"}
    assert set(request) == {
        "url",
        "base_url",
        "headers",
        "query_params",
        "path_params",
        "cookies",
        "user",
        "meta",
    }


def test_from_request():
    mock_request = MockHTTPConnection(
        url="http://localhost:8000/test?param1=value1&param2=value2",
        headers={
            "Content-Type": "application/json",
            "Cookie": "session=abc123",
        },
        path_params={"id": "123"},
    )

    request_like = HTTPRequest.from_request(mock_request)

    assert request_like["url"] == {
        "path": "/test",
        "port": 8000,
        "scheme": "http",
        "netloc": "localhost:8000",
        "query": "param1=value1&param2=value2",
        "hostname": "localhost",
    }

    assert request_like["headers"] == {
        "content-type": "application/json",
        "cookie": "session=abc123",
    }
    assert request_like["cookies"] == {"session": "abc123"}
    assert request_like["path_params"] == {"id": "123"}


def test_query_params_filtering():
    mock_request = MockHTTPConnection(
        url="http://localhost:8000/test?param1=value1&marimo_param=value2"
    )

    request_like = HTTPRequest.from_request(mock_request)

    # marimo in params is ok
    assert dict(request_like["query_params"]) == {
        "param1": ["value1"],
        "marimo_param": ["value2"],
    }


def test_header_params_filtering():
    mock_request = MockHTTPConnection(
        url="http://localhost:8000/test",
        headers={
            "Content-Type": "application/json",
            "x-marimo-param": "value1",
            "marimo-param": "value2",
        },
    )

    request_like = HTTPRequest.from_request(mock_request)

    assert request_like["headers"] == {"content-type": "application/json"}


def test_display():
    request = HTTPRequest(
        url={"path": "/test"},
        base_url={"path": "/"},
        headers={},
        query_params=defaultdict(list),
        path_params={},
        cookies={},
        user={"is_authenticated": True},
        meta={},
    )

    display_dict = request._display_()
    assert isinstance(display_dict, dict)
    assert "url" in display_dict


def test_from_request_normalizes_starlette_user():
    """Starlette BaseUser instances must be flattened to a dict so that
    HTTPRequest can be msgspec-encoded across the IPC queue boundary."""
    mock_request = MockHTTPConnection(user=SimpleUser("alice"))
    request_like = HTTPRequest.from_request(mock_request)
    assert request_like["user"] == {
        "username": "alice",
        "is_authenticated": True,
        "display_name": "alice",
    }
    # Regression for the IPC msgspec path: encoding must not raise.
    msgspec.msgpack.encode(request_like["user"])


def test_from_request_user_missing_returns_empty_dict():
    mock_request = MockHTTPConnection()
    request_like = HTTPRequest.from_request(mock_request)
    assert request_like["user"] == {}


def test_from_request_user_already_dict_passthrough():
    mock_request = MockHTTPConnection(
        user={"username": "bob", "is_authenticated": True}
    )
    request_like = HTTPRequest.from_request(mock_request)
    assert request_like["user"] == {
        "username": "bob",
        "is_authenticated": True,
    }


def test_command_msgspec_json_decode_command_with_http_request():
    """Regression for the Pyodide path: ``parse_dataclass`` builds a
    ``msgspec.json`` decoder for any Command containing an ``HTTPRequest``
    field. msgspec.json rejects unions with two array-like members, so
    ``Encodable`` must avoid e.g. ``list | tuple`` simultaneously.
    """
    from marimo._runtime.commands import ExecuteCellCommand

    # NB: ``Command`` uses ``rename="camel"``, but ``HTTPRequest`` is a
    # plain ``@dataclass`` whose fields stay snake_case on the wire.
    payload = (
        b'{"type":"execute-cell","cellId":"c1","code":"x=1","request":'
        b'{"url":{"path":"/x"},"base_url":{},"headers":{},'
        b'"query_params":{},"path_params":{},"cookies":{},"meta":{},'
        b'"user":{"username":"u","is_authenticated":true,"display_name":"u"}}}'
    )
    cmd = msgspec.json.decode(payload, type=ExecuteCellCommand)
    assert cmd.cell_id == "c1"
    assert cmd.request is not None
    assert cmd.request["user"] == {
        "username": "u",
        "is_authenticated": True,
        "display_name": "u",
    }
