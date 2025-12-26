# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations


class InvalidSessionException(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
