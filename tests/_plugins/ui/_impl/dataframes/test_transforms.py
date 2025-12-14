# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from marimo._plugins.ui._impl.dataframes.transforms.types import (
    FilterRowsTransform,
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


def test_parse_transforms_with_in_operator() -> None:
    def create_transform(operator: str):
        return {
            "transforms": [
                {
                    "type": "filter_rows",
                    "operation": "keep_rows",
                    "where": [
                        {
                            "column_id": "category",
                            "operator": operator,
                            "value": ["A", "B", "C"],
                        },
                    ],
                },
            ]
        }

    for operator in ["in", "not_in"]:
        value = create_transform(operator)
        result = parse_raw(value, Transformations)
        assert isinstance(result, Transformations)
        # Verify the value is converted to tuple for hashability
        transform = result.transforms[0]
        assert isinstance(transform, FilterRowsTransform)
        assert transform.where[0].value == ("A", "B", "C")
