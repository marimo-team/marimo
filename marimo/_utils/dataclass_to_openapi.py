# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import dataclasses
from enum import Enum
from typing import (
    Any,
    Dict,
    List,
    Literal,
    Optional,
    Type,
    Union,
    get_args,
    get_origin,
    get_type_hints,
)


def _python_type_to_openapi_type(
    py_type: Any, processed_classes: Dict[Type[Any], str]
) -> Dict[str, Any]:
    """
    Convert a Python type to an OpenAPI schema.
    """
    origin = get_origin(py_type)
    if origin is Union:
        args = get_args(py_type)
        if type(None) in args:
            non_none_args = [arg for arg in args if arg is not type(None)]
            if len(non_none_args) == 1:
                return {
                    **_python_type_to_openapi_type(
                        non_none_args[0], processed_classes
                    ),
                    "nullable": True,
                }
            else:
                return {
                    "oneOf": [
                        _python_type_to_openapi_type(arg, processed_classes)
                        for arg in non_none_args
                    ],
                    "nullable": True,
                }
        else:
            return {
                "oneOf": [
                    _python_type_to_openapi_type(arg, processed_classes)
                    for arg in args
                ]
            }
    elif origin in (list, List):
        (item_type,) = get_args(py_type)
        return {
            "type": "array",
            "items": _python_type_to_openapi_type(
                item_type, processed_classes
            ),
        }
    elif origin in (dict, Dict):
        _key_type, value_type = get_args(py_type)
        return {
            "type": "object",
            "additionalProperties": _python_type_to_openapi_type(
                value_type, processed_classes
            ),
        }
    elif origin is Literal:
        return {"enum": list(get_args(py_type))}
    elif origin is tuple:
        args = get_args(py_type)
        if len(args) == 2 and isinstance(args[1], type(Ellipsis)):
            return {
                "type": "array",
                "items": _python_type_to_openapi_type(
                    args[0], processed_classes
                ),
            }
        else:
            return {
                "type": "array",
                "prefixItems": [
                    _python_type_to_openapi_type(arg, processed_classes)
                    for arg in args
                ],
            }
    elif dataclasses.is_dataclass(py_type):
        return dataclass_to_openapi_spec(py_type, processed_classes)
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
    elif isinstance(py_type, type) and issubclass(py_type, Enum):
        return {"type": "string", "enum": [e.value for e in py_type]}
    else:
        raise ValueError(f"Unsupported type: {py_type}")


def dataclass_to_openapi_spec(
    cls: Type[Any], processed_classes: Optional[Dict[Type[Any], str]] = None
) -> Dict[str, Any]:
    """Convert a dataclass to an OpenAPI schema.

    Args:
        cls (Type[Any]): The dataclass to convert.

    Raises:
        ValueError: If cls is not a dataclass.

    Returns:
        Dict[str, Any]: The OpenAPI schema.
    """
    if processed_classes is None:
        processed_classes = {}

    if not dataclasses.is_dataclass(cls):
        raise ValueError(f"{cls} is not a dataclass")

    if cls in processed_classes:
        return {"$ref": f"#/components/schemas/{processed_classes[cls]}"}

    schema_name = cls.__name__
    processed_classes[cls] = schema_name

    fields: tuple[dataclasses.Field[Any], ...] = dataclasses.fields(cls)
    properties: Dict[str, Dict[str, Any]] = {}
    required: List[str] = []

    for field in fields:
        field_type = get_type_hints(cls)[field.name]
        properties[field.name] = _python_type_to_openapi_type(
            field_type, processed_classes
        )
        if (
            field.default is dataclasses.MISSING
            and field.default_factory is dataclasses.MISSING
            and not _is_optional(field_type)
        ):
            required.append(field.name)

    schema: Dict[str, Any] = {
        "type": "object",
        "properties": properties,
    }
    if required:
        schema["required"] = required

    return schema


def _is_optional(field: dataclasses.Field[Any]) -> bool:
    """
    Check if a field is Optional
    """
    return get_origin(field) is Union and type(None) in get_args(field)
