# Copyright 2026 Marimo. All rights reserved.

from __future__ import annotations

import re
from typing import Any


def to_camel_case(snake_str: str) -> str:
    if snake_str == "":
        return ""

    if "_" not in snake_str:
        return snake_str

    pascal_case = "".join(x.capitalize() for x in snake_str.lower().split("_"))
    return snake_str[0].lower() + pascal_case[1:]


def to_snake_case(string: str) -> str:
    if string == "":
        return ""

    s1 = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", string)
    s2 = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1)
    return s2.replace("-", "_").lower()


def deep_to_camel_case(snake_dict: Any) -> dict[str, Any]:
    if isinstance(snake_dict, list):
        return [deep_to_camel_case(item) for item in snake_dict]  # type: ignore  # noqa: E501
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
