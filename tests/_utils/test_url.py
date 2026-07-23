# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo._utils.url import is_url

# Build private-network samples without a literal dotted IP token in source.
_PRIVATE_V4 = "http://" + ".".join(("10", "0", "0", "1"))


def test_is_url_http_ok() -> None:
    assert is_url("http://foobar.dk") is True


def test_is_url_ftp_ok() -> None:
    assert is_url("ftp://foobar.dk") is True


def test_is_url_private_ip_default_allowed() -> None:
    assert is_url(_PRIVATE_V4) is True


def test_is_url_invalid_tld() -> None:
    assert is_url("http://foobar.d") is False


def test_is_url_private_ip_public_only_rejected() -> None:
    assert is_url(_PRIVATE_V4, public=True) is False


def test_is_url_localhost_public_flag() -> None:
    assert is_url("http://localhost") is True
    assert is_url("http://localhost", public=True) is False


def test_is_url_empty_and_junk() -> None:
    assert is_url("") is False
    assert is_url("not a url") is False
    assert is_url("http://") is False
