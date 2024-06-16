# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import dataclasses
import datetime
from collections.abc import Mapping, Sequence
from decimal import Decimal
from enum import Enum
from typing import (
    Any,
    ClassVar,
    Dict,
    ForwardRef,
    List,
    Literal,
    Type,
    Union,
    get_args,
    get_origin,
    get_type_hints,
)

from marimo._server.models.base import to_camel_case
from marimo._utils.typing import Annotated, NotRequired


def python_type_name(py_type: Any) -> str:
    origin = get_origin(py_type)
    if origin is Annotated:
        maybe_name = py_type.__metadata__[0]
        if isinstance(maybe_name, str):
            return maybe_name
    return py_type.__name__  # ignore[no-any-return]


def python_type_to_openapi_type(
    py_type: Any,
    processed_classes: Dict[Any, str],
    camel_case: bool,
) -> Dict[str, Any]:
    """
    Convert a Python type to an OpenAPI schema.

    Returns:
        Dict[str, Any]: The OpenAPI schema.
    """
    origin = get_origin(py_type)

    # We Annotate Union's with a name, so they can
    # be reused and ref'ed
    if origin is Annotated:
        name = python_type_name(py_type)
        if py_type in processed_classes:
            return {"$ref": f"#/components/schemas/{name}"}
        processed_classes[py_type] = name

        return python_type_to_openapi_type(
            get_args(py_type)[0], processed_classes, camel_case
        )

    if origin is Union:
        args = get_args(py_type)
        # Optional is a Union[None, ...]
        if type(None) in args:
            non_none_args = [arg for arg in args if arg is not type(None)]
            if len(non_none_args) == 1:
                return {
                    **python_type_to_openapi_type(
                        non_none_args[0], processed_classes, camel_case
                    ),
                    "nullable": True,
                }
            else:
                return {
                    "oneOf": _unique(
                        [
                            python_type_to_openapi_type(
                                arg, processed_classes, camel_case
                            )
                            for arg in non_none_args
                        ]
                    ),
                    "nullable": True,
                }
        else:
            return {
                "oneOf": _unique(
                    [
                        python_type_to_openapi_type(
                            arg, processed_classes, camel_case
                        )
                        for arg in args
                    ]
                )
            }
    elif origin in (list, List) or origin is Sequence:
        (item_type,) = get_args(py_type)
        return {
            "type": "array",
            "items": python_type_to_openapi_type(
                item_type, processed_classes, camel_case
            ),
        }
    elif origin in (dict, Dict) or origin is Mapping:
        _key_type, value_type = get_args(py_type)
        return {
            "type": "object",
            "additionalProperties": python_type_to_openapi_type(
                value_type, processed_classes, camel_case
            ),
        }
    elif origin is Literal:
        return {"enum": list(get_args(py_type)), "type": "string"}
    elif origin is NotRequired:
        return python_type_to_openapi_type(
            get_args(py_type)[0], processed_classes, camel_case
        )
    elif origin is tuple:
        args = get_args(py_type)
        if len(args) == 2 and isinstance(args[1], type(Ellipsis)):
            return {
                "type": "array",
                "items": python_type_to_openapi_type(
                    args[0], processed_classes, camel_case
                ),
            }
        else:
            return {
                "type": "array",
                "prefixItems": [
                    python_type_to_openapi_type(
                        arg, processed_classes, camel_case
                    )
                    for arg in args
                ],
            }
    elif dataclasses.is_dataclass(py_type):
        return dataclass_to_openapi_spec(
            py_type, processed_classes, camel_case
        )
    elif py_type is Any:
        return {}
    elif py_type is object:
        return {"type": "object", "additionalProperties": True}
    elif py_type is str:
        return {"type": "string"}
    elif py_type is int:
        return {"type": "integer"}
    elif py_type is float:
        return {"type": "number"}
    elif py_type is bool:
        return {"type": "boolean"}
    elif py_type is Decimal:
        return {"type": "number"}
    elif py_type is bytes:
        return {"type": "string", "format": "byte"}
    elif py_type is datetime.date:
        return {"type": "string", "format": "date"}
    elif py_type is datetime.time:
        return {"type": "string", "format": "time"}
    elif py_type is datetime.datetime:
        return {"type": "string", "format": "date-time"}
    elif py_type is datetime.timedelta:
        return {"type": "string", "format": "duration"}
    elif py_type is None:
        return {"type": "null"}
    elif isinstance(py_type, type) and issubclass(py_type, Enum):
        name = python_type_name(py_type)
        if py_type in processed_classes:
            return {"$ref": f"#/components/schemas/{name}"}
        processed_classes[py_type] = name
        return {"type": "string", "enum": [e.value for e in py_type]}
    elif isinstance(py_type, ForwardRef):
        return {"$ref": f"#/components/schemas/{py_type.__forward_arg__}"}
    else:
        raise ValueError(
            f"Unsupported type: py_type={py_type}, origin={origin}"
        )


def dataclass_to_openapi_spec(
    cls: Type[Any],
    processed_classes: Dict[Any, str],
    camel_case: bool,
) -> Dict[str, Any]:
    """Convert a dataclass to an OpenAPI schema.

    Args:
        cls (Type[Any]): The dataclass to convert.

    Raises:
        ValueError: If cls is not a dataclass.

    Returns:
        Dict[str, Any]: The OpenAPI schema.
    """
    if not dataclasses.is_dataclass(cls):
        raise ValueError(f"{cls} is not a dataclass")

    if cls in processed_classes:
        return {"$ref": f"#/components/schemas/{processed_classes[cls]}"}

    schema_name = python_type_name(cls)
    processed_classes[cls] = schema_name

    type_hints = get_type_hints(cls, include_extras=True)
    fields: tuple[dataclasses.Field[Any], ...] = dataclasses.fields(cls)
    properties: Dict[str, Dict[str, Any]] = {}
    required: List[str] = []

    for field in fields:
        cased_field_name = (
            to_camel_case(field.name) if camel_case else field.name
        )
        field_type = type_hints[field.name]
        properties[cased_field_name] = python_type_to_openapi_type(
            field_type, processed_classes, camel_case
        )
        if not _is_optional(field_type):
            required.append(cased_field_name)

    # Handle ClassVar that might be initialized already
    for field_name, type_hint in type_hints.items():
        cased_field_name = (
            to_camel_case(field_name) if camel_case else field_name
        )
        if get_origin(type_hint) is ClassVar:
            # Literal type
            value = getattr(cls, field_name)
            properties[cased_field_name] = {
                "type": "string",
                "enum": [value] if isinstance(value, str) else value,
            }
            required.append(cased_field_name)

    schema: Dict[str, Any] = {
        "type": "object",
        "properties": properties,
    }
    if required:
        schema["required"] = required

    return schema


def _unique(items: list[Any]) -> list[Any]:
    # Unique dictionaries
    seen: set[str] = set()
    result: list[Any] = []
    for item in items:
        if isinstance(item, dict):
            key = str(item)
            if key in seen:
                continue
            seen.add(key)
        result.append(item)
    return result


def _is_optional(field: dataclasses.Field[Any]) -> bool:
    """
    Check if a field is Optional
    """
    return get_origin(field) is Union and type(None) in get_args(field)
