# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import os


# Could be replaced with `find_uv_bin` from uv Python package in the future
def find_uv_bin() -> str:
    return os.environ.get("UV", "uv")
