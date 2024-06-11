from __future__ import annotations

import dataclasses
from typing import Any, List, Literal, Optional

from marimo._utils.dataclass_to_openapi import dataclass_to_openapi_spec


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
    tags: List[str]
    metadata: Any


def test_dataclass_to_openapi() -> None:
    openapi_spec = dataclass_to_openapi_spec(Person)
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
                    "kind": {"enum": ["home", "work"]},
                },
                "required": ["street", "city", "kind"],
            },
            "tags": {"type": "array", "items": {"type": "string"}},
            "metadata": {},
        },
        "required": ["name", "age", "address", "tags", "metadata"],
    }


@dataclasses.dataclass
class Node:
    value: int
    left: Optional[Node]
    right: Optional[Node]


def test_recursive_dataclass_to_openapi() -> None:
    openapi_spec = dataclass_to_openapi_spec(Node)
    assert openapi_spec == {
        "type": "object",
        "properties": {
            "value": {"type": "integer"},
            "left": {"$ref": "#/components/schemas/Node", "nullable": True},
            "right": {"$ref": "#/components/schemas/Node", "nullable": True},
        },
        "required": ["value"],
    }
