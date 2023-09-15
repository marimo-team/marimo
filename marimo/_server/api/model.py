# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

import dataclasses
import json
from typing import Any, Type, TypeVar, get_args, get_origin, get_type_hints

T = TypeVar("T")


def to_snake(string: str) -> str:
    # basic conversion of javascript camel case to snake
    # does not handle contiguous caps
    return "".join(
        ["_" + i.lower() if i.isupper() else i for i in string]
    ).lstrip("_")


def _build_value(value: Any, cls: Type[T]) -> T:
    # origin_cls is not None if cls is a container (such as list, tuple, set,
    # ...)
    origin_cls = get_origin(cls)
    if origin_cls in (list, set):
        (arg_type,) = get_args(cls)
        return origin_cls(_build_value(v, arg_type) for v in value)  # type: ignore # noqa: E501
    elif origin_cls == tuple:
        arg_types = get_args(cls)
        if len(arg_types) == 2 and isinstance(arg_types[1], type(Ellipsis)):
            return origin_cls(_build_value(v, arg_types[0]) for v in value)  # type: ignore # noqa: E501
        else:
            return origin_cls(_build_value(v, t) for v, t in zip(value, arg_types))  # type: ignore # noqa: E501
    elif origin_cls == dict:
        key_type, value_type = get_args(cls)
        return origin_cls(  # type: ignore[no-any-return]
            **{
                _build_value(k, key_type): _build_value(v, value_type)
                for k, v in value.items()
            }
        )
    elif dataclasses.is_dataclass(cls):
        return _build_dataclass(value, cls)  # type: ignore[return-value]
    else:
        return value  # type: ignore[no-any-return]


def _build_dataclass(value: dict[Any, Any], cls: Type[T]) -> T:
    types = get_type_hints(cls)
    transformed = {
        to_snake(k): _build_value(v, types[to_snake(k)])
        for k, v in value.items()
    }
    return cls(**transformed)


def parse_raw(message: bytes, cls: Type[T]) -> T:
    """Utility to parse a message as JSON, and instantiate into supplied type.

    `cls` must be a dataclass.

    Supported collection types in the dataclass:
    - List, Tuple, Set, Dict
    - for Python 3.8 compatibility, must use collection types from
      the typing module (e.g., typing.List[int] instead of list[int])

    Transforms all fields in the parsed JSON from camel case to snake case.

    Args:
    ----
    message: the message to parse
    cls: the type to instantiate
    """
    parsed = json.loads(message)
    return _build_dataclass(parsed, cls)
