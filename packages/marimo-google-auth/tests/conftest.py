"""Shared pytest fixtures."""

from __future__ import annotations

import json
import sys
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable


class FakeStdin:
    """Stand-in for marimo's ``ThreadSafeStdin`` for unit tests."""

    def __init__(
        self,
        responder: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    ) -> None:
        self._responder = responder or _default_responder
        self.requests: list[dict[str, Any]] = []

    def _request_auth(self, payload: str) -> str:
        envelope = json.loads(payload)
        self.requests.append(envelope)
        response = self._responder(envelope)
        return json.dumps(response)


def _default_responder(req: dict[str, Any]) -> dict[str, Any]:
    return {
        "protocol_version": req.get("protocol_version", 1),
        "request_id": req["request_id"],
        "status": "ok",
        "access_token": "FAKE_TEST_TOKEN",
        "expires_at": 9_999_999_999,
        "scope": " ".join(req.get("scopes") or []),
        "token_type": "Bearer",
    }


@pytest.fixture
def install_fake_stdin(monkeypatch: pytest.MonkeyPatch):
    """Patch ``sys.stdin`` with a ``FakeStdin`` for the duration of a test."""

    def _install(
        responder: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    ) -> FakeStdin:
        fake = FakeStdin(responder)
        monkeypatch.setattr(sys, "stdin", fake)
        return fake

    return _install


@pytest.fixture
def adc_paths(tmp_path, monkeypatch: pytest.MonkeyPatch):
    """Redirect ADC + sidecar paths into a tmpdir.

    Returns a ``(adc_path, sidecar_path)`` tuple. Also ensures
    ``GOOGLE_APPLICATION_CREDENTIALS`` is reset around the test.
    """
    adc_path = tmp_path / "adc.json"
    sidecar_path = tmp_path / "sidecar.json"

    # Make ``Path.home()`` resolve to tmpdir for code that uses default
    # paths, so we exercise the production path-construction logic too.
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

    # Reset the env var (test isolation).
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)

    return adc_path, sidecar_path


@pytest.fixture
def clear_auth_cache():
    """Reset the in-process token cache around a test."""
    from google.colab import auth as colab_auth

    colab_auth._clear_cache()
    yield
    colab_auth._clear_cache()


@pytest.fixture
def uninstall_patch():
    """Make sure ``_patch.install_pydata_patch`` doesn't leak across tests."""
    from google.colab import _patch

    _patch.uninstall_pydata_patch()
    yield
    _patch.uninstall_pydata_patch()


def make_scopes() -> Iterable[str]:
    """Convenience: a small deterministic scope list for tests."""
    return [
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/spreadsheets",
    ]
