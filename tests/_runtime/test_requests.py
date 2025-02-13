from __future__ import annotations

from collections import defaultdict
from typing import Any, Optional

from starlette.datastructures import URL, Headers, QueryParams
from starlette.requests import HTTPConnection

from marimo._runtime.requests import HTTPRequest


class MockHTTPConnection(HTTPConnection):
    def __init__(
        self,
        url: str = "http://localhost:8000/test?param1=value1&param2=value2",
        headers: Optional[dict[str, str]] = None,
        path_params: Optional[dict[str, Any]] = None,
    ):
        url_obj = URL(url)
        # Convert headers to list of tuples as expected by Starlette
        raw_headers = [(k.lower(), v) for k, v in (headers or {}).items()]
        scope = {
            "type": "http",
            "method": "GET",
            "headers": dict(raw_headers),
            "path": url_obj.path,
            "path_params": path_params or {},
        }
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
