# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from marimo._server.api.lifespans import _startup_url
from marimo._server.start import _resolve_proxy
from marimo._server.tokens import AuthToken


def _make_state(host: str, port: int = 2718, base_url: str = "/") -> MagicMock:
    state = MagicMock()
    state.host = host
    state.port = port
    state.base_url = base_url
    state.session_manager.auth_token = AuthToken("")  # empty = no token
    return state


@pytest.mark.parametrize(
    ("host", "expected"),
    [
        # IPv4
        ("127.0.0.1", "http://localhost:2718/"),  # loopback pretty-printed
        ("0.0.0.0", "http://0.0.0.0:2718/"),
        # Bare IPv6
        ("fd00::cafe", "http://[fd00::cafe]:2718/"),
        ("2001:db8::1", "http://[2001:db8::1]:2718/"),
        ("::1", "http://localhost:2718/"),  # loopback pretty-printed
        ("::", "http://[::]:2718/"),
        # Full non-abbreviated IPv6
        (
            "2001:0db8:85a3:0000:0000:8a2e:0370:7334",
            "http://[2001:0db8:85a3:0000:0000:8a2e:0370:7334]:2718/",
        ),
        # Bracketed IPv6 (user passed [addr])
        ("[fd00::cafe]", "http://[fd00::cafe]:2718/"),
        # Zone ID must be stripped from URL
        ("fe80::1%eth0", "http://[fe80::1]:2718/"),
        ("[fe80::1%lo0]", "http://[fe80::1]:2718/"),
    ],
)
def test_startup_url_ipv6(host: str, expected: str) -> None:
    state = _make_state(host)
    assert _startup_url(state) == expected


@pytest.mark.parametrize(
    ("proxy", "in_port", "in_host", "expected_port", "expected_host"),
    [
        # No proxy: port and host pass through unchanged
        (None, 2972, "127.0.0.1", 2972, "127.0.0.1"),
        # Bare hostname: default to port 80
        ("example.com", 2972, "127.0.0.1", 80, "example.com"),
        # host:port
        ("example.com:8080", 2972, "127.0.0.1", 8080, "example.com"),
        # http:// schema: default port 80
        ("http://example.com", 2972, "127.0.0.1", 80, "example.com"),
        # https:// schema: default port 443
        ("https://example.com", 2972, "127.0.0.1", 443, "example.com"),
        # https:// schema with explicit port
        ("https://example.com:8443", 2972, "127.0.0.1", 8443, "example.com"),
        # http:// with explicit port
        ("http://example.com:8080", 2972, "127.0.0.1", 8080, "example.com"),
        # IPv6 with brackets and port
        ("[2001:db8::1]:8080", 2972, "127.0.0.1", 8080, "2001:db8::1"),
        # Bare-port proxy (no host): port applies, host falls back to
        # the inbound host arg rather than the literal ":8080" string.
        (":8080", 2972, "0.0.0.0", 8080, "0.0.0.0"),
        # Empty string proxy is treated as "no proxy".
        ("", 2972, "127.0.0.1", 2972, "127.0.0.1"),
    ],
)
def test_resolve_proxy(
    proxy: str | None,
    in_port: int,
    in_host: str,
    expected_port: int,
    expected_host: str,
) -> None:
    port, host = _resolve_proxy(in_port, in_host, proxy)
    assert port == expected_port
    assert host == expected_host


def test_startup_url_getnameinfo_failure() -> None:
    """If getnameinfo raises (e.g. host not resolvable), URL is still valid."""
    from unittest.mock import patch

    state = _make_state("fd00::dead")
    with patch("socket.getnameinfo", side_effect=OSError("unreachable")):
        url = _startup_url(state)
    assert url == "http://[fd00::dead]:2718/"


def test_startup_url_ipv6_with_token() -> None:
    """Full IPv6 URL including access token is well-formed."""
    state = _make_state("fd00::cafe", port=2718, base_url="/")
    state.session_manager.auth_token = AuthToken("tok3n")
    url = _startup_url(state)
    assert url == "http://[fd00::cafe]:2718/?access_token=tok3n"
    # Verify it's parseable and components are correct
    from urllib.parse import urlparse

    parsed = urlparse(url)
    assert parsed.hostname == "fd00::cafe"
    assert parsed.port == 2718
    assert parsed.query == "access_token=tok3n"
