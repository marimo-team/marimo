# Copyright 2025 Marimo. All rights reserved.


def hash_code(code: str) -> str:
    import hashlib

    return hashlib.sha256(code.encode("utf-8")).hexdigest()
