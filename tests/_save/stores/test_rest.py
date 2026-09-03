# Copyright 2026 Marimo. All rights reserved.

from __future__ import annotations

import logging
import urllib.error
from typing import Any, Self
from unittest.mock import patch

from marimo import _loggers
from marimo._save.stores.rest import RestStore


def _propagate_marimo_logs(monkeypatch) -> None:
    """Let `caplog` see marimo's logger, which does not propagate by default."""
    monkeypatch.setattr(_loggers.marimo_logger(), "propagate", True)


class _Response:
    """Minimal stand-in for the object urlopen is used as a context manager."""

    def __init__(self, status: int, body: bytes = b"") -> None:
        self.status = status
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: Any) -> bool:
        return False


def _store() -> RestStore:
    return RestStore(base_url="https://example.invalid", api_key="key")


def test_get_returns_body_on_200() -> None:
    with patch("urllib.request.urlopen", return_value=_Response(200, b"data")):
        assert _store().get("key") == b"data"


def test_get_returns_none_on_client_error_status() -> None:
    with patch("urllib.request.urlopen", return_value=_Response(404)):
        assert _store().get("key") is None


def test_get_returns_none_on_http_error() -> None:
    error = urllib.error.HTTPError(
        "https://example.invalid/key", 500, "Server Error", {}, None
    )
    with patch("urllib.request.urlopen", side_effect=error):
        assert _store().get("key") is None


def test_get_logs_the_unexpected_status(monkeypatch, caplog: Any) -> None:
    """An unexpected status is reported as itself, not as a bare-raise error."""
    _propagate_marimo_logs(monkeypatch)

    with (
        caplog.at_level(logging.WARNING),
        patch("urllib.request.urlopen", return_value=_Response(204)),
    ):
        assert _store().get("key") is None

    assert "204" in caplog.text
    assert "No active exception" not in caplog.text
