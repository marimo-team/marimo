# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from marimo._plugins.ui._impl.dataframes.transforms.types import (
    Transformations,
)
from marimo._utils.parse_dataclass import parse_raw


def test_parse_transforms() -> None:
    value = {
        "transforms": [
            {
                "type": "filter_rows",
                "operation": "keep_rows",
                "where": [
                    {
                        "column_id": "student",
                        "operator": "is_false",
                    },
                    {
                        "column_id": "age",
                        "operator": "<=",
                        "value": 20,
                    },
                    {
                        "column_id": "email",
                        "operator": "ends_with",
                        "value": "@gmail.com",
                    },
                ],
            },
        ]
    }
    result = parse_raw(value, Transformations)
    assert isinstance(result, Transformations)
