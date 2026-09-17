# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import pytest

from marimo._ai._opencode import opencode_headers, require_session_id
from marimo._version import __version__


@pytest.mark.parametrize("session_id", ["chat-123", "a" * 128])
def test_require_session_id(session_id: str) -> None:
    assert require_session_id(session_id) == session_id


@pytest.mark.parametrize(
    "session_id",
    ["bad\nid", "bad id", "a" * 129, "", None],
)
def test_require_session_id_rejects(session_id: str | None) -> None:
    """OpenCode rejects requests without a session ID, so raise rather
    than omit the header."""
    with pytest.raises(ValueError):
        require_session_id(session_id)


def test_opencode_headers() -> None:
    assert opencode_headers("chat-123") == {
        "User-Agent": f"marimo/{__version__}",
        "x-opencode-client": "marimo",
        "x-opencode-session": "chat-123",
    }
