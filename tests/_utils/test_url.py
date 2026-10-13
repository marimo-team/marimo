# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import pytest

from marimo._utils.url import is_url


@pytest.mark.parametrize("port", [8, 80, 8000])
def test_is_url_accepts_various_port_lengths(port: int) -> None:
    url = f"http://127.0.0.1:{port}/macros.tex"
    assert is_url(url), f"expected is_url to accept {url!r}, got False"
