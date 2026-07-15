# Copyright 2026 Marimo. All rights reserved.

from __future__ import annotations

import re
from typing import Any


def to_camel_case(snake_str: str) -> str:
    if snake_str == "":
        return ""

    if "_" not in snake_str:
        return snake_str

    # Preserve leading underscores (e.g. "_private_key" -> "_privateKey").
    # Building the camelCase name from `snake_str[0] + pascal_case[1:]` assumed
    # the first character was the start of the first word; for a leading
    # underscore it dropped the real first letter ("_foo" -> "_oo").
    stripped = snake_str.lstrip("_")
    leading_underscores = snake_str[: len(snake_str) - len(stripped)]

    pascal_case = "".join(x.capitalize() for x in stripped.lower().split("_"))
    if not pascal_case:
        # snake_str was all underscores; leave it unchanged.
        return snake_str
    camel_case = pascal_case[0].lower() + pascal_case[1:]
    return leading_underscores + camel_case


def to_snake_case(string: str) -> str:
    if string == "":
        return ""

    s1 = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", string)
    s2 = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1)
    return s2.replace("-", "_").lower()


def deep_to_camel_case(snake_dict: Any) -> dict[str, Any]:
    if isinstance(snake_dict, list):
        return [deep_to_camel_case(item) for item in snake_dict]  # type: ignore
    if isinstance(snake_dict, str):
        return to_camel_case(snake_dict)  # type: ignore

    camel_dict: dict[str, Any] = {}
    for key, value in snake_dict.items():
        if isinstance(value, dict):
            camel_dict[to_camel_case(key)] = deep_to_camel_case(value)
        elif isinstance(value, list):
            camel_dict[to_camel_case(key)] = [
                deep_to_camel_case(item) for item in value
            ]
        else:
            camel_dict[to_camel_case(key)] = value
    return camel_dict
