# Copyright 2026 Marimo. All rights reserved.
"""Mint opaque IDs; object owners determine whether an ID is still live."""

from __future__ import annotations

import secrets
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable

_Id = TypeVar("_Id", bound=str)
_ALPHABET = "0123456789abcdefghjkmnpqrstvwxyz"


def mint(kind: Callable[[str], _Id], prefix: str) -> _Id:
    """Create a typed ID with 80 random bits in Crockford Base32."""
    body = "".join(secrets.choice(_ALPHABET) for _ in range(16))
    return kind(f"{prefix}-{body}")
