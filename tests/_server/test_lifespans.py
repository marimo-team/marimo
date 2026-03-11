# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from marimo._server.api.lifespans import _startup_url
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
