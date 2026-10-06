# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal
from numbers import Integral
from typing import Any, Final, Literal

from marimo._data.models import ColumnStats, DataType
from marimo._messaging.msgspec_encoder import encode_json_bytes
from marimo._plugins.ui._impl.tables.table_manager import (
    TableManager,
    is_missing_sample_value,
    serialize_sample_value,
)
from marimo._utils.msgspec_basestruct import BaseStruct

TABLE_FILTER_CONTEXT_MAX_BYTES: Final = 32_768
TABLE_FILTER_CONTEXT_MAX_EXAMPLES_PER_COLUMN: Final = 10
TABLE_FILTER_CONTEXT_MAX_EXAMPLE_CHARACTERS: Final = 160
TABLE_FILTER_CONTEXT_MAX_STATISTICS_ROWS: Final = 1_000_000
JS_MAX_SAFE_INTEGER: Final = 2**53 - 1
DURATION_UNITS: Final = frozenset({"ms", "ns", "μs", "s"})

StatisticName = Literal[
    "nulls",
    "min",
    "p25",
    "median",
    "p75",
    "max",
    "mean",
    "std",
    "p5",
    "p95",
]
OmissionKind = Literal["examples", "statistics", "schema"]
OmissionReason = Literal[
    "unavailable",
    "value_too_long",
    "row_count_unknown",
    "row_limit",
    "size_limit",
]

CORE_STATISTICS: Final[tuple[StatisticName, ...]] = (
    "nulls",
    "min",
    "p25",
    "median",
    "p75",
    "max",
    "mean",
)
ENRICHMENT_STATISTICS: Final[tuple[StatisticName, ...]] = (
    "std",
    "p5",
    "p95",
)
ALL_STATISTICS: Final[tuple[StatisticName, ...]] = (
    *CORE_STATISTICS,
    *ENRICHMENT_STATISTICS,
)


@dataclass(frozen=True)
class FilterContextLimits:
    """Limits for bounded table context collection."""

    max_bytes: int = TABLE_FILTER_CONTEXT_MAX_BYTES
    max_examples_per_column: int = TABLE_FILTER_CONTEXT_MAX_EXAMPLES_PER_COLUMN
    max_example_characters: int = TABLE_FILTER_CONTEXT_MAX_EXAMPLE_CHARACTERS
    max_statistics_rows: int = TABLE_FILTER_CONTEXT_MAX_STATISTICS_ROWS

    def __post_init__(self) -> None:
        if (
            min(
                self.max_bytes,
                self.max_examples_per_column,
                self.max_example_characters,
                self.max_statistics_rows,
            )
            < 0
        ):
            raise ValueError("Filter context limits must not be negative")


DEFAULT_FILTER_CONTEXT_LIMITS: Final = FilterContextLimits()


# Omit unavailable fields so empty collections and numeric zero keep meaning.
class FilterContextStatistics(BaseStruct, omit_defaults=True):
    nulls: int | float | None = None
    min: int | float | None = None
    p25: int | float | None = None
    median: int | float | None = None
    p75: int | float | None = None
    max: int | float | None = None
    mean: int | float | None = None
    std: int | float | None = None
    p5: int | float | None = None
    p95: int | float | None = None


class FilterContextColumn(BaseStruct, omit_defaults=True):
    name: str
    type: DataType
    source_type: str
    examples: list[str] | None = None
    statistics: FilterContextStatistics | None = None


class FilterContextOmission(BaseStruct, omit_defaults=True):
    kind: OmissionKind
    reason: OmissionReason
    column: str | None = None
    fields: list[StatisticName] | None = None
    count: int | None = None


class FilterContext(BaseStruct):
    """Bounded schema and value context for table-filter generation."""

    row_count: int | None
    columns: list[FilterContextColumn]
    omissions: list[FilterContextOmission]


@dataclass(frozen=True)
class _StatisticSources:
    values: dict[str, ColumnStats]


def build_filter_context(
    manager: TableManager[Any],
    limits: FilterContextLimits = DEFAULT_FILTER_CONTEXT_LIMITS,
) -> FilterContext:
    """Build context from the original table without executing lazy sources.

    Args:
        manager: Table manager that owns the original, unfiltered data.
        limits: Collection and encoded-size limits for optional context.

    Returns:
        Schema, bounded enrichment, and typed omission reasons.
    """
    row_count = manager.get_num_rows(force=False)
    column_names = manager.get_column_names()
    field_types = {
        column_name: manager.get_field_type(column_name)
        for column_name in column_names
    }
    columns = [
        FilterContextColumn(
            name=str(column_name),
            type=field_types[column_name][0],
            source_type=field_types[column_name][1],
        )
        for column_name in column_names
    ]
    context = FilterContext(
        row_count=row_count,
        columns=columns,
        omissions=[],
    )
    if _encoded_size(context) > limits.max_bytes:
        context.omissions.append(
            FilterContextOmission(kind="schema", reason="size_limit")
        )
        return context

    sample_manager = _take_example_sample(manager, limits)
    statistic_sources = _collect_statistic_sources(
        manager,
        field_types,
        row_count,
        limits,
    )
    for column_name, column in zip(column_names, columns, strict=True):
        normalized_type, _ = field_types[column_name]
        column.examples = _collect_examples(
            sample_manager,
            column_name,
            limits,
            context.omissions,
        )
        column.statistics = _collect_statistics(
            column_name,
            normalized_type,
            row_count,
            limits,
            statistic_sources,
            context.omissions,
        )

    return _apply_byte_limit(context, limits.max_bytes)


def _collect_statistic_sources(
    manager: TableManager[Any],
    field_types: dict[str, tuple[DataType, str]],
    row_count: int | None,
    limits: FilterContextLimits,
) -> _StatisticSources:
    numeric_columns = [
        column_name
        for column_name, (normalized_type, _) in field_types.items()
        if normalized_type in ("integer", "number")
    ]
    if (
        not numeric_columns
        or row_count is None
        or row_count > limits.max_statistics_rows
    ):
        return _StatisticSources(values={})

    try:
        return _StatisticSources(
            values=manager.get_stats_for_columns(numeric_columns)
        )
    except Exception:
        values: dict[str, ColumnStats] = {}
        for column_name in numeric_columns:
            try:
                values[column_name] = manager.get_stats(column_name)
            except Exception:
                pass
        return _StatisticSources(values=values)


def _take_example_sample(
    manager: TableManager[Any],
    limits: FilterContextLimits,
) -> TableManager[Any] | None:
    try:
        return manager.take(limits.max_examples_per_column, 0)
    except Exception:
        return None


def _collect_examples(
    sample_manager: TableManager[Any] | None,
    column_name: str,
    limits: FilterContextLimits,
    omissions: list[FilterContextOmission],
) -> list[str] | None:
    if sample_manager is None:
        _append_unavailable_examples_omission(omissions, column_name)
        return None

    try:
        values = sample_manager.get_sample_values(
            column_name,
            max_values=limits.max_examples_per_column,
        )
    except Exception:
        _append_unavailable_examples_omission(omissions, column_name)
        return None
    if values is None:
        _append_unavailable_examples_omission(omissions, column_name)
        return None

    examples: list[str] = []
    seen: set[str] = set()
    omitted_count = 0
    for value in values:
        if is_missing_sample_value(value):
            continue
        serialized = serialize_sample_value(value)
        text = serialized if isinstance(serialized, str) else str(serialized)
        if text in seen:
            continue
        seen.add(text)
        if len(text) > limits.max_example_characters:
            omitted_count += 1
        else:
            examples.append(text)

    if omitted_count:
        omissions.append(
            FilterContextOmission(
                kind="examples",
                reason="value_too_long",
                column=column_name,
                count=omitted_count,
            )
        )
    return examples


def _append_unavailable_examples_omission(
    omissions: list[FilterContextOmission],
    column_name: str,
) -> None:
    omissions.append(
        FilterContextOmission(
            kind="examples",
            reason="unavailable",
            column=column_name,
        )
    )


def _collect_statistics(
    column_name: str,
    normalized_type: DataType,
    row_count: int | None,
    limits: FilterContextLimits,
    sources: _StatisticSources,
    omissions: list[FilterContextOmission],
) -> FilterContextStatistics | None:
    if normalized_type not in ("integer", "number"):
        return None

    if row_count is None:
        _append_statistics_omission(
            omissions,
            column_name,
            "row_count_unknown",
            list(ALL_STATISTICS),
        )
        return None

    if row_count > limits.max_statistics_rows:
        _append_statistics_omission(
            omissions,
            column_name,
            "row_limit",
            list(ALL_STATISTICS),
        )
        return None

    source = sources.values.get(column_name)
    if source is None:
        _append_statistics_omission(
            omissions,
            column_name,
            "unavailable",
            list(ALL_STATISTICS),
        )
        return None

    values: dict[str, int | float] = {}
    unavailable: list[StatisticName] = []
    for field in ALL_STATISTICS:
        value = _coerce_js_safe_number(getattr(source, field))
        if value is None:
            unavailable.append(field)
        else:
            values[field] = value

    if unavailable:
        _append_statistics_omission(
            omissions,
            column_name,
            "unavailable",
            unavailable,
        )
    return FilterContextStatistics(**values)


def _append_statistics_omission(
    omissions: list[FilterContextOmission],
    column_name: str,
    reason: OmissionReason,
    fields: list[StatisticName],
) -> None:
    omissions.append(
        FilterContextOmission(
            kind="statistics",
            reason=reason,
            column=column_name,
            fields=fields,
        )
    )


def _coerce_js_safe_number(value: Any) -> int | float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, str):
        numeric_text, separator, unit = value.rpartition(" ")
        if not separator or unit not in DURATION_UNITS:
            return None
        try:
            return _coerce_js_safe_number(Decimal(numeric_text))
        except ValueError:
            return None
    if isinstance(value, Decimal):
        if not value.is_finite():
            return None
        if value == value.to_integral_value():
            integer = int(value)
            if abs(integer) > JS_MAX_SAFE_INTEGER:
                return None
            return integer
    if isinstance(value, Integral):
        integer = int(value)
        if abs(integer) > JS_MAX_SAFE_INTEGER:
            return None
        return integer
    try:
        numeric_value = float(value)
    except (OverflowError, TypeError, ValueError):
        return None
    if not math.isfinite(numeric_value):
        return None
    if numeric_value.is_integer() and abs(numeric_value) > JS_MAX_SAFE_INTEGER:
        return None
    return numeric_value


def _apply_byte_limit(context: FilterContext, max_bytes: int) -> FilterContext:
    current_size = _encoded_size(context)
    if current_size <= max_bytes:
        return context

    example_omission: FilterContextOmission | None = None
    for column in reversed(context.columns):
        if column.examples is None:
            continue
        if not column.examples:
            before = _encoded_size(column)
            column.examples = None
            current_size = _updated_size(current_size, column, before)
            if example_omission is None:
                example_omission = FilterContextOmission(
                    kind="examples",
                    reason="size_limit",
                )
                current_size = _append_omission(
                    context,
                    current_size,
                    example_omission,
                )
            if current_size <= max_bytes:
                return context
            continue

        while column.examples:
            before = _encoded_size(column)
            column.examples.pop()
            if not column.examples:
                column.examples = None
            current_size = _updated_size(current_size, column, before)

            if example_omission is None:
                example_omission = FilterContextOmission(
                    kind="examples",
                    reason="size_limit",
                    count=1,
                )
                current_size = _append_omission(
                    context,
                    current_size,
                    example_omission,
                )
            else:
                before = _encoded_size(example_omission)
                example_omission.count = (example_omission.count or 0) + 1
                current_size = _updated_size(
                    current_size,
                    example_omission,
                    before,
                )
            if current_size <= max_bytes:
                return context

    statistic_omissions: dict[int, FilterContextOmission] = {}
    for fields in (ENRICHMENT_STATISTICS, CORE_STATISTICS):
        for column_index in range(len(context.columns) - 1, -1, -1):
            column = context.columns[column_index]
            statistics = column.statistics
            if statistics is None:
                continue
            for field in reversed(fields):
                if getattr(statistics, field) is None:
                    continue

                before = _encoded_size(column)
                setattr(statistics, field, None)
                if not _has_statistics(statistics):
                    column.statistics = None
                current_size = _updated_size(current_size, column, before)

                omission = statistic_omissions.get(column_index)
                if omission is None:
                    omission = FilterContextOmission(
                        kind="statistics",
                        reason="size_limit",
                        column=column.name,
                        fields=[field],
                        count=1,
                    )
                    statistic_omissions[column_index] = omission
                    current_size = _append_omission(
                        context,
                        current_size,
                        omission,
                    )
                else:
                    before = _encoded_size(omission)
                    omission.fields = [field, *(omission.fields or [])]
                    omission.count = (omission.count or 0) + 1
                    current_size = _updated_size(
                        current_size,
                        omission,
                        before,
                    )
                if current_size <= max_bytes:
                    return context

    return _compact_omissions_or_report_schema(
        context,
        current_size,
        max_bytes,
    )


def _has_statistics(statistics: FilterContextStatistics) -> bool:
    return any(
        getattr(statistics, field) is not None for field in ALL_STATISTICS
    )


def _updated_size(current_size: int, item: Any, before: int) -> int:
    return current_size + _encoded_size(item) - before


def _append_omission(
    context: FilterContext,
    current_size: int,
    omission: FilterContextOmission,
) -> int:
    separator_size = 1 if context.omissions else 0
    context.omissions.append(omission)
    return current_size + separator_size + _encoded_size(omission)


def _compact_omissions_or_report_schema(
    context: FilterContext,
    current_size: int,
    max_bytes: int,
) -> FilterContext:
    def is_statistics_size_omission(
        omission: FilterContextOmission,
    ) -> bool:
        return (
            omission.kind == "statistics" and omission.reason == "size_limit"
        )

    # Preserve statistics size detail until other optional detail is exhausted.
    groups = (
        [
            omission
            for omission in reversed(context.omissions)
            if not is_statistics_size_omission(omission)
        ],
        [
            omission
            for omission in reversed(context.omissions)
            if is_statistics_size_omission(omission)
        ],
    )
    for group_index, omissions in enumerate(groups):
        fields = (
            ("fields", "count", "column")
            if group_index == 0
            else ("fields", "column")
        )
        for field in fields:
            for omission in omissions:
                if getattr(omission, field) is None:
                    continue
                before = _encoded_size(omission)
                setattr(omission, field, None)
                current_size = _updated_size(
                    current_size,
                    omission,
                    before,
                )
                if current_size <= max_bytes:
                    return context

    deduplicated: list[FilterContextOmission] = []
    seen: dict[
        tuple[
            OmissionKind, OmissionReason, str | None, tuple[StatisticName, ...]
        ],
        FilterContextOmission,
    ] = {}
    for omission in context.omissions:
        key = (
            omission.kind,
            omission.reason,
            omission.column,
            tuple(omission.fields or []),
        )
        existing = seen.get(key)
        if existing is not None:
            if omission.count is not None:
                existing.count = (existing.count or 0) + omission.count
            continue
        seen[key] = omission
        deduplicated.append(omission)
    if len(deduplicated) != len(context.omissions):
        context.omissions = deduplicated
        current_size = _encoded_size(context)
        if current_size <= max_bytes:
            return context

    context.omissions = [
        FilterContextOmission(kind="schema", reason="size_limit")
    ]
    return context


def _encoded_size(value: Any) -> int:
    return len(encode_json_bytes(value))
