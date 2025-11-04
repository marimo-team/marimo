# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations


def hash_code(code: str | None) -> str:
    import hashlib

    if code is None or code == "":
        # Return null hash for empty/missing code
        return "0" * 32  # MD5 hash length
    return hashlib.md5(code.encode("utf-8"), usedforsecurity=False).hexdigest()
