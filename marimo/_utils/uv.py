# Copyright 2025 Marimo. All rights reserved.
import os


# Could be replaced with `find_uv_bin` from uv Python package in the future
def find_uv_bin() -> str:
    return os.environ.get("UV", "uv")
