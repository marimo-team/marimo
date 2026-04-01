# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations


class InvalidSessionException(Exception):
    """Raised when a request references a session that does not exist or is no longer valid."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
