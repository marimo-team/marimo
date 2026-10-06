# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from enum import Enum, IntEnum

from marimo._utils.serialization import serialize_sample_value


def test_serialize_sample_value_normalizes_nested_enums() -> None:
    class TextEnum(str, Enum):
        VALUE = "wire-value"

    class NumberEnum(IntEnum):
        VALUE = 7

    assert {
        "text": serialize_sample_value(TextEnum.VALUE),
        "number": serialize_sample_value(NumberEnum.VALUE),
        "nested": serialize_sample_value(
            {
                TextEnum.VALUE: [TextEnum.VALUE, NumberEnum.VALUE],
            }
        ),
    } == {
        "text": "VALUE",
        "number": "VALUE",
        "nested": '{"VALUE": ["VALUE", "VALUE"]}',
    }
