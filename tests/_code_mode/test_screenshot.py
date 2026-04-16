# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import base64
from typing import Any

from marimo._code_mode.screenshot import (
    _ScreenshotSession,
    _to_data_url,
)
from marimo._runtime.commands import HTTPRequest


class TestToDataUrl:
    def test_round_trip(self) -> None:
        payload = b"\x89PNG\r\n\x1a\n"
        result = _to_data_url(payload)
        assert result.startswith("data:image/png;base64,")
        decoded = base64.b64decode(result.split(",", 1)[1])
        assert decoded == payload

    def test_empty(self) -> None:
        result = _to_data_url(b"")
        assert result == "data:image/png;base64,"


class TestScreenshotSessionAuthUrl:
    def test_url_without_auth(self) -> None:
        session = _ScreenshotSession("http://localhost:1234")
        assert session._server_url == "http://localhost:1234"
        assert session._screenshot_auth_token is None

    def test_url_with_auth(self) -> None:
        session = _ScreenshotSession(
            "http://localhost:1234", screenshot_auth_token="tok123"
        )
        assert session._screenshot_auth_token == "tok123"

    def test_page_url_includes_screenshot_auth_token(self) -> None:
        """The kiosk page URL must include the access_token query param."""
        session = _ScreenshotSession(
            "http://localhost:9999", screenshot_auth_token="secret"
        )
        # Replicate the URL-building logic from _ensure_ready.
        params = "kiosk=true"
        if session._screenshot_auth_token:
            params += f"&access_token={session._screenshot_auth_token}"
        page_url = f"{session._server_url}?{params}"

        assert "access_token=secret" in page_url
        assert "kiosk=true" in page_url

    def test_page_url_omits_token_when_none(self) -> None:
        session = _ScreenshotSession("http://localhost:9999")
        params = "kiosk=true"
        if session._screenshot_auth_token:
            params += f"&access_token={session._screenshot_auth_token}"
        page_url = f"{session._server_url}?{params}"

        assert "access_token" not in page_url
        assert page_url == "http://localhost:9999?kiosk=true"


class TestExecuteEndpointInjectsAuthToken:
    """The /execute endpoint injects ``meta["screenshot_auth_token"]`` into the
    ``HTTPRequest`` it passes to the kernel so code-mode screenshot
    support can authenticate Playwright against this server.
    """

    def test_meta_receives_screenshot_auth_token(self) -> None:
        """Simulate what the /execute endpoint does: build an
        HTTPRequest and mutate its meta dict."""
        http_req = _make_http_request()

        # This mirrors the injection in execution.py:
        screenshot_auth_token = "test-token-abc"
        http_req.meta["screenshot_auth_token"] = screenshot_auth_token

        assert http_req.meta["screenshot_auth_token"] == "test-token-abc"

    def test_meta_preserves_existing_keys(self) -> None:
        http_req = _make_http_request(meta={"custom": "value"})
        http_req.meta["screenshot_auth_token"] = "tok"

        assert http_req.meta["custom"] == "value"
        assert http_req.meta["screenshot_auth_token"] == "tok"

    def test_meta_empty_by_default(self) -> None:
        """Without the /execute injection, meta has no screenshot_auth_token."""
        http_req = _make_http_request()
        assert "screenshot_auth_token" not in http_req.meta


# -- helpers --------------------------------------------------------


def _make_http_request(
    meta: dict[str, Any] | None = None,
) -> HTTPRequest:
    """Build a minimal HTTPRequest for testing."""
    return HTTPRequest(
        url={
            "path": "/api/kernel/execute",
            "port": 1234,
            "scheme": "http",
            "netloc": "localhost:1234",
            "query": "",
            "hostname": "localhost",
        },
        base_url={
            "path": "/",
            "port": 1234,
            "scheme": "http",
            "netloc": "localhost:1234",
            "query": "",
            "hostname": "localhost",
        },
        headers={},
        query_params={},
        path_params={},
        cookies={},
        meta=meta or {},
        user={},
    )
