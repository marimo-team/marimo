# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations


def build_data_url(mimetype: str, data: bytes) -> str:
    str_repr = data.decode("utf-8").replace("\n", "")
    return f"data:{mimetype};base64,{str_repr}"


def flatten_string(text: str) -> str:
    return "".join([line.strip() for line in text.split("\n")])
