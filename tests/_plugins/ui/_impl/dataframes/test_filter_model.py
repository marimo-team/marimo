# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import pytest

from marimo._plugins.ui._impl.dataframes.transforms.types import (
    DTYPE_OPERATORS,
    FilterCondition,
    FilterGroup,
    RangeValue,
    conditions_to_filter_group,
    validate_operator_for_dtype,
)

# --- RangeValue ---


def test_range_value_int() -> None:
    rv = RangeValue(min=1, max=10)
    assert rv.min == 1
    assert rv.max == 10


def test_range_value_float() -> None:
    rv = RangeValue(min=1.5, max=10.5)
    assert rv.min == 1.5
    assert rv.max == 10.5


def test_range_value_str() -> None:
    rv = RangeValue(min="2024-01-01", max="2024-12-31")
    assert rv.min == "2024-01-01"
    assert rv.max == "2024-12-31"


def test_range_value_frozen() -> None:
    rv = RangeValue(min=1, max=10)
    with pytest.raises(AttributeError):
        rv.min = 2  # type: ignore[misc]


def test_range_value_hashable() -> None:
    rv = RangeValue(min=1, max=10)
    assert hash(rv) is not None
    s = {rv}
    assert rv in s


def test_range_value_equality() -> None:
    assert RangeValue(min=1, max=10) == RangeValue(min=1, max=10)


def test_range_value_inequality() -> None:
    assert RangeValue(min=1, max=10) != RangeValue(min=1, max=20)
    assert RangeValue(min=1, max=10) != RangeValue(min=2, max=10)


# --- FilterCondition ---


def test_condition_basic() -> None:
    fc = FilterCondition(
        type="condition", column_id="x", operator="==", value=5
    )
    assert fc.type == "condition"
    assert fc.column_id == "x"
    assert fc.operator == "=="
    assert fc.value == 5
    assert fc.negate is False


def test_condition_negate_default() -> None:
    fc = FilterCondition(
        type="condition", column_id="x", operator="==", value=5
    )
    assert fc.negate is False


def test_condition_negate_true() -> None:
    fc = FilterCondition(
        type="condition", column_id="x", operator="==", value=5, negate=True
    )
    assert fc.negate is True


def test_condition_negate_changes_hash() -> None:
    fc1 = FilterCondition(
        type="condition", column_id="x", operator="==", value=5
    )
    fc2 = FilterCondition(
        type="condition", column_id="x", operator="==", value=5, negate=True
    )
    assert hash(fc1) != hash(fc2)


def test_condition_frozen() -> None:
    fc = FilterCondition(
        type="condition", column_id="x", operator="==", value=5
    )
    with pytest.raises(AttributeError):
        fc.value = 10  # type: ignore[misc]


def test_condition_hashable() -> None:
    fc = FilterCondition(
        type="condition", column_id="x", operator="==", value=5
    )
    assert hash(fc) is not None
    s = {fc}
    assert fc in s


def test_condition_in_list_to_tuple() -> None:
    fc = FilterCondition(
        type="condition", column_id="x", operator="in", value=[1, 2, 3]
    )
    assert isinstance(fc.value, tuple)
    assert fc.value == (1, 2, 3)


def test_condition_in_tuple_passthrough() -> None:
    fc = FilterCondition(
        type="condition", column_id="x", operator="in", value=(1, 2, 3)
    )
    assert fc.value == (1, 2, 3)


def test_condition_in_invalid_value() -> None:
    with pytest.raises(ValueError, match="list or tuple"):
        FilterCondition(
            type="condition", column_id="x", operator="in", value="bad"
        )


def test_condition_not_in_list_to_tuple() -> None:
    fc = FilterCondition(
        type="condition", column_id="x", operator="not_in", value=[1, 2]
    )
    assert isinstance(fc.value, tuple)


def test_condition_between_dict_to_range_value() -> None:
    fc = FilterCondition(
        type="condition",
        column_id="x",
        operator="between",
        value={"min": 1, "max": 10},
    )
    assert isinstance(fc.value, RangeValue)
    assert fc.value.min == 1
    assert fc.value.max == 10


def test_condition_between_range_value_passthrough() -> None:
    rv = RangeValue(min=1, max=10)
    fc = FilterCondition(
        type="condition", column_id="x", operator="between", value=rv
    )
    assert fc.value is rv


def test_condition_between_missing_min() -> None:
    with pytest.raises(ValueError, match="min.*max"):
        FilterCondition(
            type="condition",
            column_id="x",
            operator="between",
            value={"max": 10},
        )


def test_condition_between_missing_max() -> None:
    with pytest.raises(ValueError, match="min.*max"):
        FilterCondition(
            type="condition",
            column_id="x",
            operator="between",
            value={"min": 1},
        )


def test_condition_value_none_for_nullcheck() -> None:
    fc = FilterCondition(type="condition", column_id="x", operator="is_null")
    assert fc.value is None


def test_condition_equality() -> None:
    fc1 = FilterCondition(
        type="condition", column_id="x", operator="==", value=5
    )
    fc2 = FilterCondition(
        type="condition", column_id="x", operator="==", value=5
    )
    assert fc1 == fc2


def test_condition_inequality() -> None:
    fc1 = FilterCondition(
        type="condition", column_id="x", operator="==", value=5
    )
    fc2 = FilterCondition(
        type="condition", column_id="x", operator="!=", value=5
    )
    assert fc1 != fc2


# --- FilterGroup ---


def test_group_defaults() -> None:
    fg = FilterGroup(type="group", operator="and", children=())
    assert fg.type == "group"
    assert fg.operator == "and"
    assert fg.children == ()
    assert fg.negate is False


def test_group_single_child() -> None:
    fc = FilterCondition(
        type="condition", column_id="x", operator="==", value=5
    )
    fg = FilterGroup(type="group", operator="and", children=(fc,))
    assert len(fg.children) == 1
    assert fg.children[0] == fc


def test_group_multiple_children() -> None:
    fc1 = FilterCondition(
        type="condition", column_id="x", operator="==", value=5
    )
    fc2 = FilterCondition(
        type="condition", column_id="y", operator=">", value=10
    )
    fg = FilterGroup(type="group", operator="and", children=(fc1, fc2))
    assert len(fg.children) == 2


def test_group_nested() -> None:
    fc1 = FilterCondition(
        type="condition", column_id="x", operator="==", value=5
    )
    fc2 = FilterCondition(
        type="condition", column_id="y", operator=">", value=10
    )
    inner = FilterGroup(type="group", operator="or", children=(fc1, fc2))
    outer = FilterGroup(type="group", operator="and", children=(inner,))
    assert len(outer.children) == 1
    assert isinstance(outer.children[0], FilterGroup)


def test_group_deeply_nested() -> None:
    fc = FilterCondition(
        type="condition", column_id="x", operator="==", value=1
    )
    level1 = FilterGroup(type="group", operator="and", children=(fc,))
    level2 = FilterGroup(type="group", operator="or", children=(level1,))
    level3 = FilterGroup(type="group", operator="and", children=(level2,))
    assert isinstance(level3.children[0], FilterGroup)
    inner = level3.children[0]
    assert isinstance(inner, FilterGroup)
    assert isinstance(inner.children[0], FilterGroup)


def test_group_list_to_tuple() -> None:
    fc = FilterCondition(
        type="condition", column_id="x", operator="==", value=5
    )
    fg = FilterGroup(type="group", operator="and", children=[fc])  # type: ignore[arg-type]
    assert isinstance(fg.children, tuple)


def test_group_hashable() -> None:
    fc = FilterCondition(
        type="condition", column_id="x", operator="==", value=5
    )
    fg = FilterGroup(type="group", operator="and", children=(fc,))
    assert hash(fg) is not None
    s = {fg}
    assert fg in s


def test_group_hashable_nested() -> None:
    fc = FilterCondition(
        type="condition", column_id="x", operator="==", value=1
    )
    inner = FilterGroup(type="group", operator="and", children=(fc,))
    outer = FilterGroup(type="group", operator="or", children=(inner, fc))
    assert hash(outer) is not None


def test_group_or() -> None:
    fg = FilterGroup(type="group", operator="or", children=())
    assert fg.operator == "or"


def test_group_negate() -> None:
    fg = FilterGroup(type="group", operator="and", children=(), negate=True)
    assert fg.negate is True


def test_group_mixed_children() -> None:
    fc = FilterCondition(
        type="condition", column_id="x", operator="==", value=5
    )
    inner = FilterGroup(type="group", operator="or", children=(fc,))
    outer = FilterGroup(type="group", operator="and", children=(fc, inner))
    assert isinstance(outer.children[0], FilterCondition)
    assert isinstance(outer.children[1], FilterGroup)


def test_group_frozen() -> None:
    fg = FilterGroup(type="group", operator="and", children=())
    with pytest.raises(AttributeError):
        fg.operator = "or"  # type: ignore[misc]


def test_group_rejects_invalid_operator() -> None:
    # The Literal["and", "or"] annotation is not enforced at runtime by
    # Python; without __post_init__ validation a bogus operator would
    # silently fall through to the default "and" combiner and produce
    # wrong rows.
    with pytest.raises(ValueError, match="must be 'and' or 'or'"):
        FilterGroup(type="group", operator="xor", children=())  # type: ignore[arg-type]


def test_condition_between_rejects_min_greater_than_max() -> None:
    # A 'between' filter with min > max matches no rows and is almost
    # certainly a caller bug — fail loudly at construction time.
    with pytest.raises(ValueError, match="min <= max"):
        FilterCondition(
            type="condition",
            column_id="x",
            operator="between",
            value={"min": 10, "max": 5},
        )


def test_condition_between_allows_equal_min_max() -> None:
    # Equal bounds are valid (matches the single boundary value).
    fc = FilterCondition(
        type="condition",
        column_id="x",
        operator="between",
        value={"min": 5, "max": 5},
    )
    assert isinstance(fc.value, RangeValue)
    assert fc.value.min == 5
    assert fc.value.max == 5


def test_condition_between_allows_string_bounds() -> None:
    # String bounds (e.g. date strings) can't be compared against numeric
    # min<=max so they're intentionally not validated — the downstream
    # engine handles the comparison.
    fc = FilterCondition(
        type="condition",
        column_id="x",
        operator="between",
        value={"min": "2024-12-31", "max": "2024-01-01"},
    )
    assert isinstance(fc.value, RangeValue)


# --- conditions_to_filter_group ---


def test_conditions_to_group_empty() -> None:
    fg = conditions_to_filter_group([])
    assert fg.type == "group"
    assert fg.operator == "and"
    assert fg.children == ()
    assert fg.negate is False


def test_conditions_to_group_single() -> None:
    fc = FilterCondition(
        type="condition", column_id="x", operator="==", value=5
    )
    fg = conditions_to_filter_group([fc])
    assert len(fg.children) == 1
    assert fg.children[0] == fc


def test_conditions_to_group_multiple() -> None:
    fc1 = FilterCondition(
        type="condition", column_id="x", operator="==", value=5
    )
    fc2 = FilterCondition(
        type="condition", column_id="y", operator=">", value=10
    )
    fg = conditions_to_filter_group([fc1, fc2])
    assert len(fg.children) == 2
    assert fg.children[0] == fc1
    assert fg.children[1] == fc2
    assert fg.operator == "and"


def test_conditions_to_group_preserves_values() -> None:
    fc = FilterCondition(
        type="condition",
        column_id="x",
        operator="in",
        value=[1, 2, 3],
        negate=True,
    )
    fg = conditions_to_filter_group([fc])
    child = fg.children[0]
    assert isinstance(child, FilterCondition)
    assert child.column_id == "x"
    assert child.operator == "in"
    assert child.value == (1, 2, 3)
    assert child.negate is True


# --- validate_operator_for_dtype ---


@pytest.mark.parametrize(
    ("dtype", "operator"),
    [
        ("number", "=="),
        ("number", "!="),
        ("number", "<"),
        ("number", ">"),
        ("number", "<="),
        ("number", ">="),
        ("number", "between"),
        ("number", "in"),
        ("number", "not_in"),
        ("number", "is_null"),
        ("number", "is_not_null"),
        ("boolean", "is_true"),
        ("boolean", "is_false"),
        ("boolean", "is_null"),
        ("boolean", "is_not_null"),
        ("str", "equals"),
        ("str", "does_not_equal"),
        ("str", "contains"),
        ("str", "regex"),
        ("str", "starts_with"),
        ("str", "ends_with"),
        ("str", "in"),
        ("str", "not_in"),
        ("str", "is_null"),
        ("str", "is_not_null"),
        ("str", "is_empty"),
        ("temporal", "=="),
        ("temporal", "!="),
        ("temporal", "<"),
        ("temporal", ">"),
        ("temporal", "<="),
        ("temporal", ">="),
        ("temporal", "between"),
        ("temporal", "is_null"),
        ("temporal", "is_not_null"),
    ],
)
def test_validate_operator_valid(dtype: str, operator: str) -> None:
    assert validate_operator_for_dtype(operator, dtype) is True


@pytest.mark.parametrize(
    ("dtype", "operator"),
    [
        ("number", "contains"),
        ("number", "starts_with"),
        ("number", "is_empty"),
        ("number", "is_true"),
        ("boolean", "=="),
        ("boolean", "between"),
        ("boolean", "contains"),
        ("boolean", "in"),
        ("boolean", "is_empty"),
        ("str", "between"),
        ("str", "<"),
        ("str", ">="),
        ("str", "is_true"),
        ("temporal", "contains"),
        ("temporal", "is_empty"),
        ("temporal", "is_true"),
        ("temporal", "in"),
    ],
)
def test_validate_operator_invalid(dtype: str, operator: str) -> None:
    assert validate_operator_for_dtype(operator, dtype) is False


def test_validate_operator_unknown_dtype() -> None:
    assert validate_operator_for_dtype("==", "unknown_type") is True
    assert validate_operator_for_dtype("contains", "foo") is True


def test_validate_between_valid_dtypes() -> None:
    assert validate_operator_for_dtype("between", "number") is True
    assert validate_operator_for_dtype("between", "temporal") is True
    assert validate_operator_for_dtype("between", "str") is False
    assert validate_operator_for_dtype("between", "boolean") is False


def test_validate_is_empty_str_only() -> None:
    assert validate_operator_for_dtype("is_empty", "str") is True
    assert validate_operator_for_dtype("is_empty", "number") is False
    assert validate_operator_for_dtype("is_empty", "boolean") is False
    assert validate_operator_for_dtype("is_empty", "temporal") is False


def test_all_dtypes_covered() -> None:
    assert set(DTYPE_OPERATORS.keys()) == {
        "number",
        "boolean",
        "str",
        "temporal",
    }
