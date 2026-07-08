# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo._utils.url import is_url


def test_accepts_common_schemes() -> None:
    assert is_url("http://foobar.dk")
    assert is_url("https://foobar.dk")
    assert is_url("ftp://foobar.dk")


def test_accepts_url_with_port_path_query_and_fragment() -> None:
    assert is_url("https://foo.com:8080/path/to?q=1&r=2#frag")


def test_accepts_ip_and_localhost_hosts() -> None:
    assert is_url("http://10.0.0.1")
    assert is_url("http://8.8.8.8")
    assert is_url("http://localhost")


def test_rejects_non_urls() -> None:
    assert not is_url("")
    assert not is_url("not a url")
    assert not is_url("foobar.dk")  # missing scheme
    assert not is_url("http://foobar.d")  # single-character TLD


def test_rejects_unsupported_scheme() -> None:
    assert not is_url("gopher://foobar.dk")


def test_public_flag_rejects_private_ip_hosts() -> None:
    # With public=True, addresses in private ranges are not accepted.
    assert not is_url("http://10.0.0.1", public=True)
    assert not is_url("http://192.168.1.1", public=True)
    assert not is_url("http://127.0.0.1", public=True)
    assert not is_url("http://localhost", public=True)


def test_public_flag_still_accepts_public_hosts() -> None:
    assert is_url("http://8.8.8.8", public=True)
    assert is_url("http://foobar.dk", public=True)


def test_public_flag_defaults_to_false() -> None:
    # Private hosts are accepted unless public is explicitly requested.
    assert is_url("http://10.0.0.1")
    assert is_url("http://10.0.0.1", public=False)
