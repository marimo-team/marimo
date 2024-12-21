# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any

import narwhals.stable.v1 as nw

if sys.version_info < (3, 11):
    from typing_extensions import TypeGuard
else:
    from typing import TypeGuard


if TYPE_CHECKING:
    from narwhals.typing import IntoFrame


def empty_df(native_df: IntoFrame) -> IntoFrame:
    """
    Get an empty dataframe with the same schema as the given dataframe.
    """
    if can_narwhalify(native_df, eager_only=True):
        df = nw.from_native(native_df, eager_only=True)
        return df[[]].to_native()
    return native_df


def assert_narwhals_dataframe(df: nw.DataFrame[Any]) -> None:
    """
    Assert that the given dataframe is a valid narwhals dataframe.
    """
    if not isinstance(df, nw.DataFrame):
        raise ValueError(f"Unsupported dataframe type. Got {type(df)}")


def assert_narwhals_series(series: nw.Series) -> None:
    """
    Assert that the given series is a valid narwhals series.
    """
    if not isinstance(series, nw.Series):
        raise ValueError(f"Unsupported series type. Got {type(series)}")


def can_narwhalify(obj: Any, eager_only: bool = False) -> TypeGuard[IntoFrame]:
    """
    Check if the given object can be narwhalified.
    """
    if obj is None:
        return False
    try:
        nw.from_native(obj, strict=True, eager_only=eager_only)  # type: ignore[call-overload]
        return True
    except TypeError:
        return False


def assert_can_narwhalify(obj: Any) -> TypeGuard[IntoFrame]:
    """
    Assert that the given object can be narwhalified.
    """
    nw.from_native(obj)
    return True


def dataframe_to_csv(df: IntoFrame) -> str:
    """
    Convert a dataframe to a CSV string.
    """
    assert_can_narwhalify(df)
    df = nw.from_native(df, strict=True)
    if isinstance(df, nw.LazyFrame):
        return str(df.collect().write_csv())
    if nw.get_level(df) == "interchange":
        # `write_csv` isn't supported by interchange-level-only
        # DataFrames, so we convert to PyArrow in this case
        csv_str = nw.from_native(df.to_arrow(), eager_only=True).write_csv()
    else:
        csv_str = df.write_csv()
    if isinstance(csv_str, bytes):
        return csv_str.decode("utf-8")
    return str(csv_str)


def is_narwhals_integer_type(
    dtype: Any,
) -> TypeGuard[
    nw.Int64
    | nw.UInt64
    | nw.Int32
    | nw.UInt32
    | nw.Int16
    | nw.UInt16
    | nw.Int8
    | nw.UInt8
]:
    """
    Check if the given dtype is integer type.
    """
    return bool(
        dtype == nw.Int64
        or dtype == nw.UInt64
        or dtype == nw.Int32
        or dtype == nw.UInt32
        or dtype == nw.Int16
        or dtype == nw.UInt16
        or dtype == nw.Int8
        or dtype == nw.UInt8
    )


def is_narwhals_temporal_type(
    dtype: Any,
) -> TypeGuard[nw.Datetime | nw.Date]:
    """
    Check if the given dtype is temporal type.
    """
    return bool(dtype == nw.Datetime or dtype == nw.Date)


def is_narwhals_string_type(
    dtype: Any,
) -> TypeGuard[nw.String | nw.Categorical | nw.Enum]:
    """
    Check if the given dtype is string type.
    """
    return bool(
        dtype == nw.String or dtype == nw.Categorical or dtype == nw.Enum
    )


def unwrap_narwhals_dataframe(df: Any) -> Any:
    """
    Unwrap a narwhals dataframe.
    """
    if isinstance(df, nw.DataFrame):
        return df.to_native()  # type: ignore[return-value]
    return df


def unwrap_py_scalar(value: Any) -> Any:
    """
    Convert a narwhals value to a python scalar if possible, otherwise return
    the value as is.
    """
    try:
        return nw.to_py_scalar(value)
    except ValueError:
        return value
