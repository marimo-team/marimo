# Copyright 2026 Marimo. All rights reserved.

from marimo._utils.url import is_url


def test_is_url_with_single_digit_port():
    """Regression test for single-digit ports being rejected."""
    assert is_url("http://127.0.0.1:8/macros.tex")
    assert is_url("http://localhost:8")
    assert is_url("http://example.com:8/path")


def test_is_url_with_multi_digit_ports():
    assert is_url("http://127.0.0.1:80/macros.tex")
    assert is_url("http://127.0.0.1:8000/macros.tex")
    assert is_url("http://example.com:443")


def test_is_url_without_port():
    assert is_url("http://example.com")
    assert is_url("https://example.com/path")


def test_is_url_invalid():
    assert not is_url("not-a-url")
    assert not is_url("http://")
    assert not is_url("ftp://")
