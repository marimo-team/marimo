# Copyright 2023 Marimo. All rights reserved.
import json
from typing import Type, TypeVar

T = TypeVar("T")


def to_snake(string: str) -> str:
    # basic conversion of javascript camel case to snake
    # does not handle contiguous caps
    return "".join(
        ["_" + i.lower() if i.isupper() else i for i in string]
    ).lstrip("_")


def parse_raw(message: bytes, cls: Type[T]) -> T:
    """Utility to parse a message as JSON, and instantiate into supplied type.

    Transforms all fields in the parsed JSON from camel case to snake case.

    Args:
    ----
    message: the message to parse
    cls: the type to instantiate
    """
    parsed = json.loads(message)
    transformed = {to_snake(k): v for k, v in parsed.items()}
    return cls(**transformed)
