# Copyright 2026 Marimo. All rights reserved.
"""Shared URL fetch for WASM fallbacks."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict, cast

if TYPE_CHECKING:
    import ssl


class RequestKwargs(TypedDict, total=False):
    data: bytes | None
    headers: dict[str, str]
    origin_req_host: str
    unverifiable: bool
    method: str


class UrlOpenKwargs(TypedDict, total=False):
    data: bytes | None
    timeout: float
    context: ssl.SSLContext | None


def fetch_url_bytes(
    url: str,
    *,
    request_kwargs: RequestKwargs | None = None,
    urlopen_kwargs: UrlOpenKwargs | None = None,
) -> bytes:
    """Sync fetch via urllib — works in pyodide thanks to pyodide_http's
    patch_all (installed at marimo startup), which routes urllib through JS
    fetch. Single sync path for text and binary.
    """
    import urllib.request

    request = urllib.request.Request(url, **(request_kwargs or {}))
    with urllib.request.urlopen(request, **(urlopen_kwargs or {})) as response:
        return cast(bytes, response.read())
