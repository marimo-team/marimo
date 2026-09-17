# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import re

from marimo._version import __version__

# OpenCode uses the session ID for routing and prompt caching. It is sent as an
# HTTP header, so keep it to a conservative, header-safe character set.
_SESSION_ID_CHARSET = r"[A-Za-z0-9._-]{1,128}"
_SESSION_ID_RE = re.compile(_SESSION_ID_CHARSET)

# The same charset as a `msgspec` pattern, to validate a conversation ID at
# the API boundary. `msgspec` matches with `re.search`, so anchor with
# `\A`/`\Z`; `$` would let a trailing newline through.
SESSION_ID_PATTERN = rf"\A{_SESSION_ID_CHARSET}\Z"

# OpenCode asks clients to identify themselves rather than rely on a generic
# SDK user agent. https://opencode.ai/docs/go/#where-can-i-use-it
_CLIENT_HEADERS = {
    "User-Agent": f"marimo/{__version__}",
    "x-opencode-client": "marimo",
}


def require_session_id(session_id: str | None) -> str:
    """Return the session ID, or raise if it cannot be sent as a header.

    OpenCode rejects requests that omit the session ID, so a missing or
    malformed ID is an error rather than something to leave out.
    """
    if session_id and _SESSION_ID_RE.fullmatch(session_id):
        return session_id
    raise ValueError(
        f"OpenCode requires a session ID matching {_SESSION_ID_CHARSET}, "
        f"got {session_id!r}"
    )


def opencode_headers(session_id: str) -> dict[str, str]:
    """Headers OpenCode expects from clients, including the session ID."""
    return {**_CLIENT_HEADERS, "x-opencode-session": session_id}
