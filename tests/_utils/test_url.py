# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import pytest

from marimo._utils.url import is_url


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:8/macros.tex",
        "http://127.0.0.1:80/macros.tex",
        "http://127.0.0.1:8000/macros.tex",
        "http://127.0.0.1:65535/macros.tex",
    ],
)
def test_is_url_accepts_valid_ports(url: str) -> None:
    assert is_url(url)
