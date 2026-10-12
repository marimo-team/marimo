# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import json
from decimal import Decimal
from typing import Any, cast
from unittest.mock import Mock, call

import pytest

import marimo._plugins.ui._impl.tables.filter_context as filter_context_module
from marimo._data.models import ColumnStats, DataType
from marimo._messaging.msgspec_encoder import encode_json_bytes
from marimo._plugins.ui._impl.tables.filter_context import (
    ALL_STATISTICS,
    JS_MAX_SAFE_INTEGER,
    FilterContext,
    FilterContextColumn,
    FilterContextLimits,
    FilterContextOmission,
    FilterContextStatistics,
    OmissionReason,
    build_filter_context,
)
from marimo._plugins.ui._impl.tables.table_manager import TableManager
from marimo._plugins.ui._impl.tables.utils import get_table_manager
from marimo._runtime.control_flow import MarimoStopError


def make_manager(
    *,
    row_count: int | None,
    columns: dict[str, tuple[DataType, str]],
    examples: dict[str, list[Any]] | None = None,
    statistics: dict[str, ColumnStats] | None = None,
) -> TableManager[Any]:
    manager = Mock(spec=TableManager)
    sample_manager = Mock(spec=TableManager)
    manager.get_num_rows.return_value = row_count
    manager.get_column_names.return_value = list(columns)
    manager.get_field_type.side_effect = columns.__getitem__
    manager.take.return_value = sample_manager

    def get_sample_values(
        column: str,
        max_values: int,
    ) -> list[Any] | None:
        return list((examples or {}).get(column, [])[:max_values])

    sample_manager.get_sample_values.side_effect = get_sample_values
    manager.get_stats_for_columns.return_value = statistics or {}
    return cast(TableManager[Any], manager)


def complete_stats() -> ColumnStats:
    return ColumnStats(
        nulls=0,
        min=1,
        p25=2,
        median=3,
        p75=4,
        max=5,
        mean=3.0,
        std=1.5,
        p5=1.0,
        p95=5.0,
    )


def complete_filter_context_stats() -> FilterContextStatistics:
    return FilterContextStatistics(
        nulls=0,
        min=1,
        p25=2,
        median=3,
        p75=4,
        max=5,
        mean=3.0,
        std=1.5,
        p5=1.0,
        p95=5.0,
    )


def test_build_complete_filter_context() -> None:
    manager = make_manager(
        row_count=3,
        columns={
            "score": ("integer", "Int64"),
            "label": ("string", "String"),
        },
        examples={"score": [1, 2, 3], "label": ["a", "b", "c"]},
        statistics={"score": complete_stats()},
    )

    context = build_filter_context(manager)

    assert context == FilterContext(
        row_count=3,
        columns=[
            FilterContextColumn(
                name="score",
                type="integer",
                source_type="Int64",
                examples=["1", "2", "3"],
                statistics=complete_filter_context_stats(),
            ),
            FilterContextColumn(
                name="label",
                type="string",
                source_type="String",
                examples=["a", "b", "c"],
            ),
        ],
        omissions=[],
    )
    manager.get_num_rows.assert_called_once_with(force=False)
    manager.take.assert_called_once_with(10, 0)
    sample_manager = manager.take.return_value
    sample_manager.get_sample_values.assert_any_call("score", max_values=10)
    sample_manager.get_sample_values.assert_any_call("label", max_values=10)
    manager.get_stats_for_columns.assert_called_once_with(["score"])


def test_collects_numeric_statistics_in_one_batch() -> None:
    manager = make_manager(
        row_count=3,
        columns={
            "score": ("integer", "Int64"),
            "ratio": ("number", "Float64"),
            "label": ("string", "String"),
        },
        statistics={
            "score": complete_stats(),
            "ratio": complete_stats(),
        },
    )

    context = build_filter_context(manager)

    assert context == FilterContext(
        row_count=3,
        columns=[
            FilterContextColumn(
                name="score",
                type="integer",
                source_type="Int64",
                examples=[],
                statistics=complete_filter_context_stats(),
            ),
            FilterContextColumn(
                name="ratio",
                type="number",
                source_type="Float64",
                examples=[],
                statistics=complete_filter_context_stats(),
            ),
            FilterContextColumn(
                name="label",
                type="string",
                source_type="String",
                examples=[],
            ),
        ],
        omissions=[],
    )
    manager.get_stats_for_columns.assert_called_once_with(["score", "ratio"])
    manager.get_stats.assert_not_called()


def test_records_unavailable_examples_when_sampling_fails() -> None:
    manager = make_manager(
        row_count=1,
        columns={
            "score": ("string", "String"),
            "label": ("string", "String"),
        },
    )
    manager.take.side_effect = RuntimeError("sample failed")

    context = build_filter_context(manager)

    assert context == FilterContext(
        row_count=1,
        columns=[
            FilterContextColumn(
                name="score",
                type="string",
                source_type="String",
            ),
            FilterContextColumn(
                name="label",
                type="string",
                source_type="String",
            ),
        ],
        omissions=[
            FilterContextOmission(
                kind="examples",
                reason="unavailable",
                column="score",
            ),
            FilterContextOmission(
                kind="examples",
                reason="unavailable",
                column="label",
            ),
        ],
    )
    assert json.loads(encode_json_bytes(context)) == {
        "row_count": 1,
        "columns": [
            {"name": "score", "type": "string", "source_type": "String"},
            {"name": "label", "type": "string", "source_type": "String"},
        ],
        "omissions": [
            {"kind": "examples", "reason": "unavailable", "column": "score"},
            {"kind": "examples", "reason": "unavailable", "column": "label"},
        ],
    }
    manager.take.assert_called_once_with(10, 0)


def test_distinguishes_empty_and_unavailable_examples() -> None:
    manager = make_manager(
        row_count=0,
        columns={
            "empty": ("string", "String"),
            "broken": ("string", "String"),
        },
    )
    sample_manager = manager.take.return_value

    def get_sample_values(
        column: str,
        max_values: int,
    ) -> list[Any] | None:
        del max_values
        if column == "broken":
            return None
        return []

    sample_manager.get_sample_values.side_effect = get_sample_values

    context = build_filter_context(manager)

    assert json.loads(encode_json_bytes(context)) == {
        "row_count": 0,
        "columns": [
            {
                "name": "empty",
                "type": "string",
                "source_type": "String",
                "examples": [],
            },
            {"name": "broken", "type": "string", "source_type": "String"},
        ],
        "omissions": [
            {
                "kind": "examples",
                "reason": "unavailable",
                "column": "broken",
            }
        ],
    }


def test_keeps_distinct_non_null_examples_in_stable_order() -> None:
    manager = make_manager(
        row_count=6,
        columns={"label": ("string", "String")},
        examples={"label": [None, "a", "a", None, "b", "a"]},
    )

    context = build_filter_context(manager)

    assert context == FilterContext(
        row_count=6,
        columns=[
            FilterContextColumn(
                name="label",
                type="string",
                source_type="String",
                examples=["a", "b"],
            )
        ],
        omissions=[],
    )


def test_excludes_backend_missing_values_but_keeps_literal_strings() -> None:
    pd = pytest.importorskip("pandas")
    data = pd.DataFrame(
        {
            "nullable_string": pd.Series(
                [pd.NA, "a", pd.NA, pd.NA], dtype="string"
            ),
            "datetime": [
                pd.NaT,
                pd.Timestamp("2024-01-01"),
                pd.NaT,
                pd.NaT,
            ],
            "sentinel_strings": ["None", "nan", "<NA>", "NaT"],
        }
    )
    manager = get_table_manager(data)

    context = build_filter_context(manager)

    assert context == FilterContext(
        row_count=4,
        columns=[
            FilterContextColumn(
                name="nullable_string",
                type="string",
                source_type="string",
                examples=["a"],
            ),
            FilterContextColumn(
                name="datetime",
                type="datetime",
                source_type=str(data["datetime"].dtype),
                examples=["2024-01-01 00:00:00"],
            ),
            FilterContextColumn(
                name="sentinel_strings",
                type="string",
                source_type=str(data["sentinel_strings"].dtype),
                examples=["None", "nan", "<NA>", "NaT"],
            ),
        ],
        omissions=[],
    )


def _assert_lazy_string_examples_are_unavailable(data: Any) -> None:
    manager = get_table_manager(data)
    normalized_type, source_type = manager.get_field_type("value")

    context = build_filter_context(manager)

    assert context == FilterContext(
        row_count=manager.get_num_rows(force=False),
        columns=[
            FilterContextColumn(
                name="value",
                type=normalized_type,
                source_type=source_type,
            )
        ],
        omissions=[
            FilterContextOmission(
                kind="examples",
                reason="unavailable",
                column="value",
            )
        ],
    )


def test_does_not_collect_examples_from_lazy_polars() -> None:
    pl = pytest.importorskip("polars")
    source = pl.DataFrame({"value": ["a", None, "a", "b"]})

    class LazySourceCollected(BaseException):
        pass

    def fail_on_collect(frame: Any) -> Any:
        del frame
        raise LazySourceCollected("lazy source was collected")

    _assert_lazy_string_examples_are_unavailable(
        source.lazy().map_batches(fail_on_collect, schema=source.schema)
    )


def test_does_not_collect_examples_from_duckdb() -> None:
    duckdb = pytest.importorskip("duckdb")
    _assert_lazy_string_examples_are_unavailable(
        duckdb.sql(
            "SELECT * FROM (VALUES ('a'), (NULL), ('a'), ('b')) t(value)"
        )
    )


def test_does_not_collect_examples_from_ibis() -> None:
    ibis = pytest.importorskip("ibis")
    _assert_lazy_string_examples_are_unavailable(
        ibis.memtable({"value": ["a", None, "a", "b"]})
    )


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(KeyboardInterrupt(), id="keyboard-interrupt"),
        pytest.param(MarimoStopError(None), id="marimo-stop"),
    ],
)
@pytest.mark.parametrize("operation", ["take", "examples", "statistics"])
def test_does_not_swallow_control_flow_exceptions(
    operation: str,
    error: BaseException,
) -> None:
    manager = make_manager(
        row_count=1,
        columns={"score": ("integer", "Int64")},
        examples={"score": [1]},
        statistics={"score": complete_stats()},
    )
    if operation == "take":
        manager.take.side_effect = error
    elif operation == "examples":
        manager.take.return_value.get_sample_values.side_effect = error
    else:
        manager.get_stats_for_columns.side_effect = error

    with pytest.raises(type(error)):
        build_filter_context(manager)


def test_records_unavailable_and_nonfinite_statistics() -> None:
    manager = make_manager(
        row_count=3,
        columns={"score": ("number", "Float64")},
        statistics={
            "score": ColumnStats(
                nulls=0,
                min=float("nan"),
                median=2.0,
                p75=float("inf"),
                max=3.0,
                mean=2.0,
                p5=1.0,
                p95=3.0,
            )
        },
    )

    context = build_filter_context(manager)

    assert context == FilterContext(
        row_count=3,
        columns=[
            FilterContextColumn(
                name="score",
                type="number",
                source_type="Float64",
                examples=[],
                statistics=FilterContextStatistics(
                    nulls=0,
                    median=2.0,
                    max=3.0,
                    mean=2.0,
                    p5=1.0,
                    p95=3.0,
                ),
            )
        ],
        omissions=[
            FilterContextOmission(
                kind="statistics",
                reason="unavailable",
                column="score",
                fields=["min", "p25", "p75", "std"],
            )
        ],
    )


def test_collects_numeric_duration_statistics() -> None:
    pl = pytest.importorskip("polars")
    manager = get_table_manager(
        pl.DataFrame(
            {
                "duration": pl.Series(
                    [86_400_000_000, 172_800_000_000],
                    dtype=pl.Duration("us"),
                )
            }
        )
    )

    context = build_filter_context(manager)

    assert context == FilterContext(
        row_count=2,
        columns=[
            FilterContextColumn(
                name="duration",
                type="number",
                source_type="duration[μs]",
                examples=["1 day, 0:00:00", "2 days, 0:00:00"],
                statistics=FilterContextStatistics(
                    nulls=0,
                    min=86_400_000_000,
                    max=172_800_000_000,
                    mean=129_600_000_000.0,
                ),
            )
        ],
        omissions=[
            FilterContextOmission(
                kind="statistics",
                reason="unavailable",
                column="duration",
                fields=["p25", "median", "p75", "std", "p5", "p95"],
            )
        ],
    )


@pytest.mark.parametrize(
    ("values", "row_count", "nulls"),
    [
        ([], 0, 0),
        ([None, None], 2, 2),
    ],
)
def test_records_unavailable_empty_duration_statistics(
    values: list[None],
    row_count: int,
    nulls: int,
) -> None:
    pl = pytest.importorskip("polars")
    manager = get_table_manager(
        pl.DataFrame(
            {
                "duration": pl.Series(values, dtype=pl.Duration("us")),
            }
        )
    )

    context = build_filter_context(manager)

    assert context == FilterContext(
        row_count=row_count,
        columns=[
            FilterContextColumn(
                name="duration",
                type="number",
                source_type="duration[μs]",
                examples=[],
                statistics=FilterContextStatistics(nulls=nulls),
            )
        ],
        omissions=[
            FilterContextOmission(
                kind="statistics",
                reason="unavailable",
                column="duration",
                fields=[
                    "min",
                    "p25",
                    "median",
                    "p75",
                    "max",
                    "mean",
                    "std",
                    "p5",
                    "p95",
                ],
            )
        ],
    )


def test_records_javascript_unsafe_integer_statistics_as_unavailable() -> None:
    manager = make_manager(
        row_count=3,
        columns={"score": ("integer", "Int64")},
        statistics={
            "score": ColumnStats(
                nulls=0,
                min=-(JS_MAX_SAFE_INTEGER + 1),
                p25=1,
                median=2,
                p75=3,
                max=JS_MAX_SAFE_INTEGER + 1,
                mean=2.0,
                std=1.0,
                p5=1,
                p95=3,
            )
        },
    )

    context = build_filter_context(manager)

    assert context == FilterContext(
        row_count=3,
        columns=[
            FilterContextColumn(
                name="score",
                type="integer",
                source_type="Int64",
                examples=[],
                statistics=FilterContextStatistics(
                    nulls=0,
                    p25=1,
                    median=2,
                    p75=3,
                    mean=2.0,
                    std=1.0,
                    p5=1,
                    p95=3,
                ),
            )
        ],
        omissions=[
            FilterContextOmission(
                kind="statistics",
                reason="unavailable",
                column="score",
                fields=["min", "max"],
            )
        ],
    )


def test_records_javascript_unsafe_decimal_statistics_as_unavailable() -> None:
    manager = make_manager(
        row_count=3,
        columns={"score": ("number", "Decimal(20, 0)")},
        statistics={
            "score": ColumnStats(
                nulls=0,
                min=Decimal(JS_MAX_SAFE_INTEGER + 1),
                p25=float(JS_MAX_SAFE_INTEGER + 1),
                median=float(JS_MAX_SAFE_INTEGER + 3),
                p75=float(JS_MAX_SAFE_INTEGER + 5),
                max=Decimal(JS_MAX_SAFE_INTEGER + 2),
                mean=float(JS_MAX_SAFE_INTEGER + 3),
                std=Decimal("0.5"),
                p5=float(JS_MAX_SAFE_INTEGER + 1),
                p95=float(JS_MAX_SAFE_INTEGER + 5),
            )
        },
    )

    context = build_filter_context(manager)

    assert context == FilterContext(
        row_count=3,
        columns=[
            FilterContextColumn(
                name="score",
                type="number",
                source_type="Decimal(20, 0)",
                examples=[],
                statistics=FilterContextStatistics(
                    nulls=0,
                    std=0.5,
                ),
            )
        ],
        omissions=[
            FilterContextOmission(
                kind="statistics",
                reason="unavailable",
                column="score",
                fields=[
                    "min",
                    "p25",
                    "median",
                    "p75",
                    "max",
                    "mean",
                    "p5",
                    "p95",
                ],
            )
        ],
    )


def test_records_lossy_fractional_decimal_as_unavailable() -> None:
    manager = make_manager(
        row_count=1,
        columns={"score": ("number", "Decimal(20, 1)")},
        statistics={
            "score": ColumnStats(
                nulls=0,
                min=1,
                p25=1,
                median=1,
                p75=1,
                max=1,
                mean=Decimal("9007199254740991.1"),
                std=0,
                p5=1,
                p95=1,
            )
        },
    )

    context = build_filter_context(manager)

    assert context == FilterContext(
        row_count=1,
        columns=[
            FilterContextColumn(
                name="score",
                type="number",
                source_type="Decimal(20, 1)",
                examples=[],
                statistics=FilterContextStatistics(
                    nulls=0,
                    min=1,
                    p25=1,
                    median=1,
                    p75=1,
                    max=1,
                    std=0,
                    p5=1,
                    p95=1,
                ),
            )
        ],
        omissions=[
            FilterContextOmission(
                kind="statistics",
                reason="unavailable",
                column="score",
                fields=["mean"],
            )
        ],
    )


def test_retries_statistics_per_column_when_batch_fails() -> None:
    manager = make_manager(
        row_count=3,
        columns={
            "score": ("integer", "Int64"),
            "ratio": ("number", "Float64"),
        },
    )
    manager.get_stats_for_columns.side_effect = RuntimeError("stats failed")
    manager.get_stats.side_effect = lambda column: (
        complete_stats()
        if column == "score"
        else (_ for _ in ()).throw(OverflowError("ratio failed"))
    )

    context = build_filter_context(manager)

    assert context == FilterContext(
        row_count=3,
        columns=[
            FilterContextColumn(
                name="score",
                type="integer",
                source_type="Int64",
                examples=[],
                statistics=complete_filter_context_stats(),
            ),
            FilterContextColumn(
                name="ratio",
                type="number",
                source_type="Float64",
                examples=[],
            ),
        ],
        omissions=[
            FilterContextOmission(
                kind="statistics",
                reason="unavailable",
                column="ratio",
                fields=list(ALL_STATISTICS),
            ),
        ],
    )
    manager.get_stats_for_columns.assert_called_once_with(["score", "ratio"])
    assert manager.get_stats.call_args_list == [call("score"), call("ratio")]


def test_batch_failure_preserves_healthy_pyarrow_statistics() -> None:
    pa = pytest.importorskip("pyarrow")
    manager = get_table_manager(
        pa.table(
            {
                "healthy": pa.array([1, 2], pa.int64()),
                "bad": pa.array([2**64 - 1, 1], pa.uint64()),
            }
        )
    )

    context = build_filter_context(manager)

    assert context == FilterContext(
        row_count=2,
        columns=[
            FilterContextColumn(
                name="healthy",
                type="integer",
                source_type="Int64",
                examples=["1", "2"],
                statistics=FilterContextStatistics(
                    nulls=0,
                    min=1,
                    median=1.5,
                    max=2,
                    mean=1.5,
                    std=0.7071067811865476,
                ),
            ),
            FilterContextColumn(
                name="bad",
                type="integer",
                source_type="UInt64",
                examples=["18446744073709551615", "1"],
            ),
        ],
        omissions=[
            FilterContextOmission(
                kind="statistics",
                reason="unavailable",
                column="healthy",
                fields=["p25", "p75", "p5", "p95"],
            ),
            FilterContextOmission(
                kind="statistics",
                reason="unavailable",
                column="bad",
                fields=list(ALL_STATISTICS),
            ),
        ],
    )


@pytest.mark.parametrize(
    ("row_count", "max_statistics_rows", "reason"),
    [
        (None, 1_000_000, "row_count_unknown"),
        (11, 10, "row_limit"),
    ],
)
def test_records_statistics_row_guards(
    row_count: int | None,
    max_statistics_rows: int,
    reason: OmissionReason,
) -> None:
    manager = make_manager(
        row_count=row_count,
        columns={"score": ("integer", "Int64")},
    )

    context = build_filter_context(
        manager,
        FilterContextLimits(max_statistics_rows=max_statistics_rows),
    )

    assert context == FilterContext(
        row_count=row_count,
        columns=[
            FilterContextColumn(
                name="score",
                type="integer",
                source_type="Int64",
                examples=[],
            )
        ],
        omissions=[
            FilterContextOmission(
                kind="statistics",
                reason=reason,
                column="score",
                fields=list(ALL_STATISTICS),
            )
        ],
    )
    manager.get_stats_for_columns.assert_not_called()


def test_skips_long_examples_and_records_failures() -> None:
    manager = make_manager(
        row_count=2,
        columns={"label": ("string", "String")},
        examples={"label": ["short", "x" * 11]},
    )

    context = build_filter_context(
        manager,
        FilterContextLimits(max_example_characters=10),
    )

    assert context == FilterContext(
        row_count=2,
        columns=[
            FilterContextColumn(
                name="label",
                type="string",
                source_type="String",
                examples=["short"],
            )
        ],
        omissions=[
            FilterContextOmission(
                kind="examples",
                reason="value_too_long",
                column="label",
                count=1,
            )
        ],
    )


def test_byte_limit_drops_empty_examples_without_omission() -> None:
    manager = make_manager(
        row_count=1,
        columns={"label": ("string", "String")},
    )
    expected = FilterContext(
        row_count=1,
        columns=[
            FilterContextColumn(
                name="label",
                type="string",
                source_type="String",
            )
        ],
        omissions=[],
    )

    context = build_filter_context(
        manager,
        FilterContextLimits(max_bytes=len(encode_json_bytes(expected))),
    )

    assert context == expected


def test_byte_limit_removes_data_in_priority_order() -> None:
    manager = make_manager(
        row_count=10,
        columns={"score": ("integer", "Int64")},
        examples={"score": [f"example-{index}" for index in range(10)]},
        statistics={"score": complete_stats()},
    )
    expected_without_examples = FilterContext(
        row_count=10,
        columns=[
            FilterContextColumn(
                name="score",
                type="integer",
                source_type="Int64",
                statistics=complete_filter_context_stats(),
            )
        ],
        omissions=[
            FilterContextOmission(
                kind="examples",
                reason="size_limit",
                count=10,
            )
        ],
    )
    without_examples = build_filter_context(
        manager,
        FilterContextLimits(
            max_bytes=len(encode_json_bytes(expected_without_examples))
        ),
    )

    assert without_examples == expected_without_examples

    expected_without_optional_data = FilterContext(
        row_count=10,
        columns=[
            FilterContextColumn(
                name="score",
                type="integer",
                source_type="Int64",
            )
        ],
        omissions=[
            FilterContextOmission(
                kind="examples",
                reason="size_limit",
            ),
            FilterContextOmission(
                kind="statistics",
                reason="size_limit",
                column="score",
                count=10,
            ),
        ],
    )
    without_optional_data = build_filter_context(
        manager,
        FilterContextLimits(
            max_bytes=len(encode_json_bytes(expected_without_optional_data))
        ),
    )

    assert without_optional_data == expected_without_optional_data


def test_statistics_size_omissions_keep_column_and_fields() -> None:
    large_number = 10**15
    manager = make_manager(
        row_count=10,
        columns={"score": ("integer", "Int64")},
        statistics={
            "score": ColumnStats(
                nulls=large_number,
                min=large_number,
                p25=large_number,
                median=large_number,
                p75=large_number,
                max=large_number,
                mean=large_number,
                std=large_number,
                p5=large_number,
                p95=large_number,
            )
        },
    )
    expected = FilterContext(
        row_count=10,
        columns=[
            FilterContextColumn(
                name="score",
                type="integer",
                source_type="Int64",
                statistics=FilterContextStatistics(
                    nulls=large_number,
                    min=large_number,
                    p25=large_number,
                ),
            )
        ],
        omissions=[
            FilterContextOmission(
                kind="statistics",
                reason="size_limit",
                column="score",
                fields=["median", "p75", "max", "mean", "std", "p5", "p95"],
                count=7,
            ),
        ],
    )
    context = build_filter_context(
        manager,
        FilterContextLimits(max_bytes=len(encode_json_bytes(expected))),
    )

    assert context == expected


def test_compacts_omissions_before_reporting_schema_overflow() -> None:
    columns = {f"score_{index}": ("integer", "Int64") for index in range(100)}
    manager = make_manager(row_count=None, columns=columns)
    schema_columns = [
        FilterContextColumn(
            name=column_name,
            type="integer",
            source_type="Int64",
        )
        for column_name in columns
    ]
    compact_context = FilterContext(
        row_count=None,
        columns=schema_columns,
        omissions=[
            FilterContextOmission(
                kind="statistics",
                reason="row_count_unknown",
            ),
        ],
    )
    max_bytes = len(encode_json_bytes(compact_context))

    context = build_filter_context(
        manager,
        FilterContextLimits(max_bytes=max_bytes),
    )

    assert context == compact_context
    assert len(encode_json_bytes(context)) <= max_bytes


def test_reports_schema_overflow_instead_of_deleting_typed_omissions() -> None:
    manager = make_manager(
        row_count=None,
        columns={"score": ("integer", "Int64")},
    )
    schema_only = FilterContext(
        row_count=None,
        columns=[
            FilterContextColumn(
                name="score",
                type="integer",
                source_type="Int64",
            )
        ],
        omissions=[],
    )

    context = build_filter_context(
        manager,
        FilterContextLimits(max_bytes=len(encode_json_bytes(schema_only))),
    )

    assert context == FilterContext(
        row_count=None,
        columns=schema_only.columns,
        omissions=[FilterContextOmission(kind="schema", reason="size_limit")],
    )


@pytest.mark.parametrize("lazy", [False, True], ids=["eager", "lazy"])
def test_byte_limit_encoding_work_scales_subquadratically(
    lazy: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pl = pytest.importorskip("polars") if lazy else None
    real_encode = encode_json_bytes

    def encoded_work(column_count: int) -> int:
        total_bytes = 0

        def tracked_encode(value: Any) -> bytes:
            nonlocal total_bytes
            encoded = real_encode(value)
            total_bytes += len(encoded)
            return encoded

        monkeypatch.setattr(
            filter_context_module,
            "encode_json_bytes",
            tracked_encode,
        )
        values = [f"value-{index}-" + ("x" * 40) for index in range(10)]
        if pl is None:
            columns = {
                f"column_{index}": ("string", "String")
                for index in range(column_count)
            }
            examples = dict.fromkeys(columns, values)
            manager = make_manager(
                row_count=10,
                columns=columns,
                examples=examples,
            )
        else:
            manager = get_table_manager(
                pl.DataFrame(
                    {
                        f"column_{index}": values
                        for index in range(column_count)
                    }
                ).lazy()
            )

        build_filter_context(manager, FilterContextLimits(max_bytes=0))
        return total_bytes

    small_work = encoded_work(80)
    large_work = encoded_work(160)

    assert large_work < small_work * 3


def test_reports_schema_overflow_without_dropping_schema() -> None:
    column_name = "column-" + ("x" * 200)
    manager = make_manager(
        row_count=1,
        columns={column_name: ("integer", "Int64")},
        examples={column_name: [1]},
        statistics={column_name: complete_stats()},
    )

    context = build_filter_context(
        manager,
        FilterContextLimits(max_bytes=32),
    )

    assert context == FilterContext(
        row_count=1,
        columns=[
            FilterContextColumn(
                name=column_name,
                type="integer",
                source_type="Int64",
            )
        ],
        omissions=[FilterContextOmission(kind="schema", reason="size_limit")],
    )
    assert len(encode_json_bytes(context)) > 32
    manager.take.assert_not_called()
    manager.get_stats_for_columns.assert_not_called()


def test_rejects_negative_limits() -> None:
    with pytest.raises(
        ValueError, match="Filter context limits must not be negative"
    ):
        FilterContextLimits(max_bytes=-1)
