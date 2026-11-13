# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import datetime
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Literal, cast

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins.ui._impl.dataframes.transforms.apply import (
    apply_transforms_to_df,
)
from marimo._plugins.ui._impl.dataframes.transforms.types import (
    FilterCondition,
    FilterGroup,
    FilterRowsTransform,
    TransformType,
)
from marimo._plugins.ui._impl.tables.utils import get_table_manager
from tests._data.mocks import create_dataframes

CONFORMANCE_PATH = (
    Path(__file__).resolve().parents[4]
    / "marimo/_server/ai/table_filter_conformance_cases.json"
)


def _decode_value(data_type: str, value: Any) -> Any:
    if value is None:
        return None
    if data_type == "date":
        return datetime.date.fromisoformat(value)
    if data_type == "datetime":
        return datetime.datetime.fromisoformat(value)
    if data_type == "time":
        return datetime.time.fromisoformat(value)
    return value


def _table_data(suite: dict[str, Any]) -> dict[str, Sequence[Any]]:
    columns = suite["table"]["columns"]
    data: dict[str, list[Any]] = {"row_id": []}
    for column in columns:
        data[str(column["column_id"])] = []

    for row in suite["table"]["rows"]:
        data["row_id"].append(row["row_id"])
        for column in columns:
            column_id = str(column["column_id"])
            data[column_id].append(
                _decode_value(
                    column["data_type"],
                    row["values"][column_id],
                )
            )
    return cast(dict[str, Sequence[Any]], data)


def _filter_group(value: dict[str, Any]) -> FilterGroup:
    children: list[FilterCondition | FilterGroup] = []
    for child in value["children"]:
        if child["type"] == "group":
            children.append(_filter_group(child))
        else:
            children.append(FilterCondition(**child))
    return FilterGroup(
        children=tuple(children),
        operator=value["operator"],
        negate=value["negate"],
    )


@pytest.mark.parametrize("backend", ["pandas", "polars"])
def test_table_ai_filter_conformance_cases(
    backend: Literal["pandas", "polars"],
) -> None:
    dependency = (
        DependencyManager.pandas
        if backend == "pandas"
        else DependencyManager.polars
    )
    if not dependency.has():
        pytest.skip(f"{backend} is not installed")

    suite = json.loads(CONFORMANCE_PATH.read_text())
    dataframes = create_dataframes(
        _table_data(suite),
        include=[backend],
    )
    assert len(dataframes) == 1

    for case in suite["cases"]:
        filtered = apply_transforms_to_df(
            dataframes[0],
            FilterRowsTransform(
                type=TransformType.FILTER_ROWS,
                where=_filter_group(case["expected_filter"]),
                operation="keep_rows",
            ),
        )
        rows = json.loads(get_table_manager(filtered).to_json_str())
        actual_row_ids = {row["row_id"] for row in rows}
        expected_row_ids = set(case["expected_row_ids"])

        assert len(rows) == len(expected_row_ids), case["id"]
        assert actual_row_ids == expected_row_ids, case["id"]
