# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo._plugins.ui._impl.dataframes.transforms.types import (
    FilterCondition,
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
                "where": {
                    "type": "group",
                    "operator": "and",
                    "children": [
                        {
                            "type": "condition",
                            "column_id": "student",
                            "operator": "is_false",
                        },
                        {
                            "type": "condition",
                            "column_id": "age",
                            "operator": "<=",
                            "value": 20,
                        },
                        {
                            "type": "condition",
                            "column_id": "email",
                            "operator": "ends_with",
                            "value": "@gmail.com",
                        },
                    ],
                },
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
                    "where": {
                        "type": "group",
                        "operator": "and",
                        "children": [
                            {
                                "type": "condition",
                                "column_id": "category",
                                "operator": operator,
                                "value": ["A", "B", "C"],
                            },
                        ],
                    },
                },
            ]
        }

    for operator in ["in", "not_in"]:
        value = create_transform(operator)
        result = parse_raw(value, Transformations)
        assert isinstance(result, Transformations)
        transform = result.transforms[0]
        assert isinstance(transform, FilterRowsTransform)
        condition = transform.where.children[0]
        assert isinstance(condition, FilterCondition)
        assert condition.value == ("A", "B", "C")
