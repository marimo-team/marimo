# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import Literal

import msgspec
import pytest

from marimo._cli.development.schema import _generate_schema_components
from marimo._types.ids import CellId_t


class Payload(msgspec.Struct, rename="camel"):
    cell_id: CellId_t


class Read(msgspec.Struct, tag="read"):
    payload: Payload


class Write(msgspec.Struct, tag="write"):
    payloads: list[Payload]


def test_named_union_preserves_discriminator_and_transitive_brands() -> None:
    schemas = _generate_schema_components([], {"Action": Read | Write})

    assert sorted(
        schemas["Action"]["anyOf"], key=lambda schema: schema["$ref"]
    ) == [
        {"$ref": "#/components/schemas/Read"},
        {"$ref": "#/components/schemas/Write"},
    ]
    assert schemas["Action"]["discriminator"] == {
        "propertyName": "type",
        "mapping": {
            "read": "#/components/schemas/Read",
            "write": "#/components/schemas/Write",
        },
    }
    assert schemas["Payload"] == {
        "title": "Payload",
        "type": "object",
        "properties": {"cellId": {"$ref": "#/components/schemas/CellId"}},
        "required": ["cellId"],
    }
    assert schemas["CellId"] == {"type": "string", "format": "cell-id"}


def test_brands_in_dependencies_reachable_only_through_lists() -> None:
    schemas = _generate_schema_components([], {"Write": Write})

    assert schemas["Write"]["properties"]["payloads"] == {
        "type": "array",
        "items": {"$ref": "#/components/schemas/Payload"},
    }
    assert schemas["Payload"]["properties"]["cellId"] == {
        "$ref": "#/components/schemas/CellId"
    }
    assert schemas["CellId"] == {"type": "string", "format": "cell-id"}


def test_named_literal() -> None:
    schemas = _generate_schema_components(
        [], {"Status": Literal["ready", "running"]}
    )

    assert schemas["Status"] == {"enum": ["ready", "running"]}


def test_exporting_a_struct_under_its_own_name() -> None:
    schemas = _generate_schema_components([], {"Payload": Payload})

    assert schemas["Payload"] == {
        "title": "Payload",
        "type": "object",
        "properties": {"cellId": {"$ref": "#/components/schemas/CellId"}},
        "required": ["cellId"],
    }


@pytest.mark.parametrize("name", ["Payload", "CellId"])
def test_export_name_cannot_overwrite_a_dependency(name: str) -> None:
    with pytest.raises(ValueError, match=f"Schema export '{name}' conflicts"):
        _generate_schema_components([Payload], {name: Literal["other"]})
