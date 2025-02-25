from __future__ import annotations

import dataclasses
import sys
from typing import Any, ClassVar, Literal, Optional, TypedDict, Union

import pytest

from marimo._utils.dataclass_to_openapi import (
    PythonTypeToOpenAPI,
)


@dataclasses.dataclass
class Address:
    street: str
    city: str
    zip_code: Optional[int]
    kind: Literal["home", "work"]


@dataclasses.dataclass
class Person:
    name: str
    age: int
    address: Address
    tags: list[str]
    metadata: Any


def test_dataclass_to_openapi() -> None:
    openapi_spec = PythonTypeToOpenAPI(
        name_overrides={}, camel_case=False
    ).convert(Person, processed_classes={})
    assert openapi_spec == {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "age": {"type": "integer"},
            "address": {
                "type": "object",
                "properties": {
                    "street": {"type": "string"},
                    "city": {"type": "string"},
                    "zip_code": {"type": "integer", "nullable": True},
                    "kind": {"enum": ["home", "work"], "type": "string"},
                },
                "required": ["street", "city", "kind"],
            },
            "tags": {"type": "array", "items": {"type": "string"}},
            "metadata": {},
        },
        "required": ["name", "age", "address", "tags", "metadata"],
    }


def test_dataclass_to_openapi_with_camelcase() -> None:
    openapi_spec = PythonTypeToOpenAPI(
        name_overrides={}, camel_case=True
    ).convert(Address, processed_classes={})
    assert openapi_spec == {
        "type": "object",
        "properties": {
            "street": {"type": "string"},
            "city": {"type": "string"},
            "zipCode": {"type": "integer", "nullable": True},
            "kind": {"enum": ["home", "work"], "type": "string"},
        },
        "required": ["street", "city", "kind"],
    }


@dataclasses.dataclass
class Node:
    value: int
    left: Optional[Node]
    right: Optional[Node]


def test_recursive_dataclass_to_openapi() -> None:
    openapi_spec = PythonTypeToOpenAPI(
        name_overrides={}, camel_case=False
    ).convert(Node, processed_classes={})
    assert openapi_spec == {
        "type": "object",
        "properties": {
            "value": {"type": "integer"},
            "left": {"$ref": "#/components/schemas/Node", "nullable": True},
            "right": {"$ref": "#/components/schemas/Node", "nullable": True},
        },
        "required": ["value"],
    }


Colors = Union[Literal["red"], Literal["green"], Literal["blue"]]


def test_named_union() -> None:
    openapi_spec = PythonTypeToOpenAPI(
        name_overrides={}, camel_case=False
    ).convert(Colors, processed_classes={})
    assert openapi_spec == {
        "oneOf": [
            {"enum": ["red"], "type": "string"},
            {"enum": ["green"], "type": "string"},
            {"enum": ["blue"], "type": "string"},
        ]
    }


@dataclasses.dataclass
class Theme:
    primary_color: Colors
    secondary_color: Optional[Colors]


def test_nested_named_union() -> None:
    openapi_spec = PythonTypeToOpenAPI(
        name_overrides={Colors: "colors"}, camel_case=False
    ).convert(Theme, {Colors: "colors"})
    assert openapi_spec == {
        "type": "object",
        "properties": {
            "primary_color": {"$ref": "#/components/schemas/colors"},
            "secondary_color": {
                "$ref": "#/components/schemas/colors",
                "nullable": True,
            },
        },
        "required": ["primary_color"],
    }


@dataclasses.dataclass
class Dog:
    name: ClassVar[str] = "dog"


def test_class_var() -> None:
    openapi_spec = PythonTypeToOpenAPI(
        name_overrides={}, camel_case=False
    ).convert(Dog, {})
    assert openapi_spec == {
        "type": "object",
        "properties": {"name": {"type": "string", "enum": ["dog"]}},
        "required": ["name"],
    }


def test_optional() -> None:
    openapi_spec = PythonTypeToOpenAPI(
        name_overrides={}, camel_case=False
    ).convert(Optional[str], {})
    assert openapi_spec == {
        "type": "string",
        "nullable": True,
    }


if sys.version_info >= (3, 11):
    from typing import NotRequired


@pytest.mark.skipif(
    sys.version_info < (3, 11), reason="Not supported in Python < 3.11"
)
def test_not_required() -> None:
    class NotRequiredDict(TypedDict):
        not_required_item: NotRequired[str]
        optional_item: Optional[str]

    openapi_spec = PythonTypeToOpenAPI(
        name_overrides={}, camel_case=False
    ).convert(NotRequiredDict, {})
    assert openapi_spec == {
        "type": "object",
        "properties": {
            "optional_item": {"type": "string", "nullable": True},
            "not_required_item": {"type": "string"},
        },
        "required": ["optional_item"],
    }


@pytest.mark.skipif(
    sys.version_info < (3, 11), reason="Not supported in Python < 3.11"
)
def test_not_required_total_false() -> None:
    class NotRequiredDictTotalFalse(TypedDict, total=False):
        not_required_item: NotRequired[str]
        optional_item: Optional[str]

    openapi_spec = PythonTypeToOpenAPI(
        name_overrides={}, camel_case=False
    ).convert(NotRequiredDictTotalFalse, {})
    assert openapi_spec == {
        "type": "object",
        "properties": {
            "optional_item": {"type": "string", "nullable": True},
            "not_required_item": {"type": "string"},
        },
    }


@pytest.mark.skipif(
    sys.version_info < (3, 11), reason="Not supported in Python < 3.11"
)
def test_not_required_as_dataclass() -> None:
    @dataclasses.dataclass
    class NotRequiredDictAsDataclass(TypedDict):
        not_required_item: NotRequired[str]
        optional_item: Optional[str]

    openapi_spec = PythonTypeToOpenAPI(
        name_overrides={}, camel_case=False
    ).convert(NotRequiredDictAsDataclass, {})

    assert NotRequiredDictAsDataclass(optional_item="hello") is not None

    assert openapi_spec == {
        "type": "object",
        "properties": {
            "optional_item": {"type": "string", "nullable": True},
            "not_required_item": {"type": "string"},
        },
        "required": ["optional_item"],
    }


@pytest.mark.skipif(
    sys.version_info < (3, 11), reason="Not supported in Python < 3.11"
)
def test_not_required_as_dataclass_total_false() -> None:
    @dataclasses.dataclass
    class NotRequiredDictAsDataclassTotalFalse(TypedDict, total=False):
        not_required_item: NotRequired[str]
        optional_item: Optional[str]

    openapi_spec = PythonTypeToOpenAPI(
        name_overrides={}, camel_case=False
    ).convert(NotRequiredDictAsDataclassTotalFalse, {})

    assert (
        NotRequiredDictAsDataclassTotalFalse(optional_item="hello") is not None
    )

    assert openapi_spec == {
        "type": "object",
        "properties": {
            "optional_item": {"type": "string", "nullable": True},
            "not_required_item": {"type": "string"},
        },
    }
