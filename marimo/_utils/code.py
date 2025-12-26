# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations


def hash_code(code: str) -> str:
    import hashlib

    return hashlib.md5(code.encode("utf-8"), usedforsecurity=False).hexdigest()
