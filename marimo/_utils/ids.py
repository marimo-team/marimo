# Copyright 2026 Marimo. All rights reserved.
"""Ids in the shape Hub uses: a type prefix, a dash, and 80 random bits.

The bits are written in Crockford Base32, so an id is sixteen lowercase
characters that are safe in URLs and file names and have no look-alike
letters. `rt-0f3k...` is a session, `nb-...` a notebook, and so on.
"""

from __future__ import annotations

import secrets

from marimo._types.ids import StableSessionId

_ALPHABET = "0123456789abcdefghjkmnpqrstvwxyz"


def new_id(prefix: str) -> str:
    """Returns a fresh id such as `nb-7c1e9a3f5b2d4e8a`."""
    body = "".join(secrets.choice(_ALPHABET) for _ in range(16))
    return f"{prefix}-{body}"


def new_stable_session_id() -> StableSessionId:
    """Returns a fresh identity for a session, such as `rt-7c1e9a3f5b2d4e8a`.

    Whoever creates a session chooses the id, so a kernel that continues
    an earlier one can keep it.
    """
    # NB: the host protocol calls this object a runtime, hence the prefix.
    return StableSessionId(new_id("rt"))
