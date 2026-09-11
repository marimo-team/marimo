# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import re
import sys
from typing import Any
from unittest.mock import patch

import narwhals.stable.v2 as nw
import pytest

from marimo._plugins import ui
from marimo._plugins.ui._impl.dataframes.dataframe import GetDataFrameError
from marimo._plugins.ui._impl.dataframes.transforms.handlers import (
    NarwhalsTransformHandler,
)
from marimo._plugins.ui._impl.dataframes.transforms.types import (
    Transformations,
)
from marimo._runtime.context import get_context
from marimo._runtime.functions import EmptyArgs
from marimo._utils.narwhals_utils import make_lazy
from marimo._utils.parse_dataclass import parse_raw
from tests._data.mocks import create_dataframes


@pytest.fixture(params=create_dataframes({"a": [1, 2, 3], "b": [4, 5, 6]}))
def df(request: pytest.FixtureRequest) -> Any:
    return request.param


INVALID_TRANSFORMS = [
    (
        {
            "type": "group_by",
            "column_ids": [],
            "aggregation_column_ids": [],
            "aggregation": "count",
            "drop_na": False,
        },
        "Group By",
        "column_ids",
    ),
    (
        {"type": "explode_columns", "column_ids": []},
        "Explode Columns",
        "column_ids",
    ),
    (
        {"type": "unique", "column_ids": [], "keep": "first"},
        "Unique",
        "column_ids",
    ),
    (
        {"type": "sample_rows", "n": 4, "replace": False, "seed": 1},
        "Sample Rows",
        "3 rows",
    ),
    (
        {"type": "rename_column", "column_id": "a", "new_column_id": "b"},
        "Rename Column",
        "'b' already exists",
    ),
    (
        {
            "type": "pivot",
            "column_ids": ["a"],
            "index_column_ids": [],
            "value_column_ids": [],
            "aggregation": "sum",
        },
        "Pivot",
        "index_column_ids",
    ),
]


@pytest.mark.parametrize(("payload", "name", "message"), INVALID_TRANSFORMS)
def test_handler_validation(
    df: Any, payload: dict[str, Any], name: str, message: str
) -> None:
    del name
    transforms = parse_raw({"transforms": [payload]}, Transformations)
    handler = getattr(NarwhalsTransformHandler, f"handle_{payload['type']}")
    lazy_df, _ = make_lazy(df)
    with pytest.raises(
        (ValueError, nw.exceptions.InvalidOperationError), match=message
    ):
        handler(lazy_df, transforms.transforms[0])


@pytest.mark.parametrize(("payload", "name", "message"), INVALID_TRANSFORMS)
@pytest.mark.usefixtures("executing_kernel")
def test_replayed_error_is_attributed_silent_and_recoverable(
    df: Any,
    payload: dict[str, Any],
    name: str,
    message: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    subject = ui.dataframe(df)
    rpc = get_context().function_registry.get_function(
        subject._id, "get_dataframe"
    )
    assert rpc is not None
    print("user output")
    print("user stderr", file=sys.stderr)
    with patch("marimo._runtime.functions.LOGGER.error") as log_error:
        for _ in range(2):
            subject._update({"transforms": [payload]})
            response = rpc({})
            assert isinstance(response, GetDataFrameError)
            assert re.search(f"Step 1 .*{name}.*{message}", response.error)
        subject._update({"transforms": []})
        assert rpc({}).total_rows == 3
        log_error.assert_not_called()
    captured = capsys.readouterr()
    assert captured.out == "user output\n"
    assert captured.err == "user stderr\n"


def test_incremental_error_uses_absolute_step_number(df: Any) -> None:
    subject = ui.dataframe(df)
    first = {"type": "select_columns", "column_ids": ["a", "b"]}
    subject._update({"transforms": [first]})
    subject._update({"transforms": [first, INVALID_TRANSFORMS[3][0]]})
    response = subject._get_dataframe(EmptyArgs())
    assert isinstance(response, GetDataFrameError)
    assert re.search("Step 2 .*Sample Rows.*3 rows", response.error)


@pytest.mark.parametrize("with_transform", [False, True])
def test_display_error_is_retryable(df: Any, with_transform: bool) -> None:
    subject = ui.dataframe(df)
    if with_transform:
        subject._update(
            {"transforms": [{"type": "select_columns", "column_ids": ["a"]}]}
        )
    with patch.object(
        subject,
        "_get_dataframe_response",
        side_effect=RuntimeError("temporary encoding failure"),
    ) as response:
        for _ in range(2):
            result = subject._get_dataframe(EmptyArgs())
            assert result == GetDataFrameError(
                "Error displaying dataframe: temporary encoding failure"
            )
        assert response.call_count == 2
    assert subject._get_dataframe(EmptyArgs()).total_rows == 3


def test_same_name_rename(df: Any) -> None:
    subject = ui.dataframe(df)
    subject._update(
        {
            "transforms": [
                {
                    "type": "rename_column",
                    "column_id": "a",
                    "new_column_id": "a",
                },
            ]
        }
    )
    assert subject._get_dataframe(EmptyArgs()).total_rows == 3


@pytest.mark.parametrize(
    "df",
    create_dataframes(
        {"a": [1, 2, 3]}, include=["pandas", "polars", "lazy-polars"]
    ),
)
def test_sample_with_replacement(df: Any) -> None:
    subject = ui.dataframe(df)
    subject._update(
        {
            "transforms": [
                {"type": "sample_rows", "n": 4, "replace": True, "seed": 1},
            ]
        }
    )
    assert subject._get_dataframe(EmptyArgs()).total_rows == 4


@pytest.mark.parametrize("lazy", [False, True])
@pytest.mark.parametrize(
    "next_transform",
    [
        {"type": "rename_column", "column_id": "b", "new_column_id": "c"},
        {"type": "sample_rows", "n": 1, "replace": False, "seed": 1},
    ],
)
def test_deferred_error_names_the_failing_step(
    lazy: bool,
    next_transform: dict[str, Any],
    capsys: pytest.CaptureFixture[str],
) -> None:
    pl = pytest.importorskip("polars")
    df = pl.DataFrame({"a": ["bad"], "b": [1]})
    subject = ui.dataframe(df.lazy() if lazy else df)
    payload = {
        "transforms": [
            {
                "type": "column_conversion",
                "column_id": "a",
                "data_type": "int64",
                "errors": "raise",
            },
            next_transform,
        ]
    }
    for _ in range(2):
        subject._update(payload)
        response = subject._get_dataframe(EmptyArgs())
        assert isinstance(response, GetDataFrameError)
        assert re.search("Step 1 .*Column Conversion", response.error)
    assert capsys.readouterr().err == ""
    subject._update({"transforms": []})
    assert subject._get_dataframe(EmptyArgs()).total_rows == 1


def test_failure_keeps_the_previous_valid_data(df: Any) -> None:
    subject = ui.dataframe(df)
    subject._update(
        {"transforms": [{"type": "select_columns", "column_ids": ["a"]}]}
    )
    previous = subject.value
    subject._update({"transforms": [INVALID_TRANSFORMS[3][0]]})
    assert subject.value is previous
