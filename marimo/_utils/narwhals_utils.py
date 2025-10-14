# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any, Union, overload

import narwhals as nw_main
import narwhals.dtypes as nw_dtypes
import narwhals.stable.v1 as nw1
import narwhals.stable.v2 as nw
from narwhals.typing import IntoDataFrame

if sys.version_info < (3, 11):
    from typing_extensions import TypeGuard
else:
    from typing import TypeGuard


if TYPE_CHECKING:
    from narwhals.typing import IntoDataFrame, IntoFrame, IntoLazyFrame
    from typing_extensions import TypeIs


@overload
def empty_df(native_df: IntoDataFrame) -> IntoDataFrame: ...


@overload
def empty_df(native_df: IntoLazyFrame) -> IntoLazyFrame: ...


def empty_df(
    native_df: Union[IntoDataFrame, IntoLazyFrame],
) -> Union[IntoDataFrame, IntoLazyFrame]:
    """
    Get an empty dataframe with the same schema as the given dataframe.
    """
    if can_narwhalify(native_df):
        df = nw.from_native(native_df)
        return df.head(0).to_native()
    return native_df


def assert_narwhals_dataframe_or_lazyframe(
    df: nw.DataFrame[Any] | nw.LazyFrame[Any],
) -> None:
    """
    Assert that the given dataframe is a valid narwhals dataframe or lazyframe.
    """
    if not is_narwhals_dataframe(df) and not is_narwhals_lazyframe(df):
        raise ValueError(f"Unsupported dataframe type. Got {type(df)}")


def assert_narwhals_series(series: nw.Series) -> None:
    """
    Assert that the given series is a valid narwhals series.
    """
    if not isinstance(series, nw.Series):
        raise ValueError(f"Unsupported series type. Got {type(series)}")


def can_narwhalify(
    obj: Any, *, eager_only: bool = False
) -> TypeGuard[IntoFrame]:
    """
    Check if the given object can be narwhalified.
    """
    if obj is None:
        return False
    try:
        nw.from_native(obj, pass_through=False, eager_only=eager_only)  # type: ignore[call-overload]
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
    df = nw.from_native(df, pass_through=False)
    df = upgrade_narwhals_df(df)
    if is_narwhals_lazyframe(df):
        return df.collect().write_csv()
    else:
        return df.write_csv()


def is_narwhals_integer_type(
    dtype: Any,
) -> TypeGuard[nw_dtypes.IntegerType]:
    """
    Check if the given dtype is integer type.
    """
    if hasattr(dtype, "is_integer"):
        return dtype.is_integer()  # type: ignore[no-any-return]
    return False


def is_narwhals_temporal_type(
    dtype: Any,
) -> TypeGuard[nw_dtypes.TemporalType]:
    """
    Check if the given dtype is temporal type.
    """
    if hasattr(dtype, "is_temporal"):
        return dtype.is_temporal()  # type: ignore[no-any-return]
    return False


def is_narwhals_time_type(dtype: Any) -> bool:
    """
    Check if the given dtype is Time
    This was added in later version, so we need to safely check
    """
    if getattr(nw, "Time", None) is not None:
        return dtype == nw.Time  # type: ignore[attr-defined,no-any-return]
    return False


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
    if is_narwhals_dataframe(df):
        return df.to_native()  # type: ignore[return-value]
    if is_narwhals_lazyframe(df):
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


def can_narwhalify_lazyframe(df: Any) -> TypeGuard[Any]:
    """
    Check if the given object is a narwhals lazyframe.
    """
    try:
        nw_df = nw.from_native(df, pass_through=False, eager_only=False)
        return is_narwhals_lazyframe(nw_df)
    except Exception:
        return False


@overload
def upgrade_narwhals_df(df: nw.DataFrame[Any]) -> nw.DataFrame[Any]: ...


@overload
def upgrade_narwhals_df(df: nw.LazyFrame[Any]) -> nw.LazyFrame[Any]: ...


def upgrade_narwhals_df(
    df: Union[nw.DataFrame[Any], nw.LazyFrame[Any]],
) -> Union[nw.DataFrame[Any], nw.LazyFrame[Any]]:
    """
    Upgrade a narwhals dataframe to the latest version.
    """
    return nw_main.from_native(df.to_native())  # type: ignore[no-any-return]


@overload
def downgrade_narwhals_df_to_v1(
    df: nw.LazyFrame[Any],
) -> nw.LazyFrame[Any]: ...


@overload
def downgrade_narwhals_df_to_v1(
    df: nw.DataFrame[Any],
) -> nw.DataFrame[Any]: ...


def downgrade_narwhals_df_to_v1(
    df: Union[nw.DataFrame[Any], nw.LazyFrame[Any]],
) -> Union[nw.DataFrame[Any], nw.LazyFrame[Any]]:
    """
    Downgrade a narwhals dataframe to the latest version.
    """
    if is_narwhals_lazyframe(df) or is_narwhals_dataframe(df):
        return nw1.from_native(df.to_native())  # type: ignore[no-any-return]
    # Pass through
    return df


def is_narwhals_lazyframe(df: Any) -> TypeIs[nw.LazyFrame[Any]]:
    """
    Check if the given object is a narwhals lazyframe.

    Checks both v1 and main.
    """
    return (
        isinstance(df, nw.LazyFrame)
        or isinstance(df, nw_main.LazyFrame)
        or isinstance(df, nw1.LazyFrame)
    )


def is_narwhals_dataframe(df: Any) -> TypeIs[nw.DataFrame[Any]]:
    """
    Check if the given object is a narwhals dataframe.

    Checks both v1 and main.
    """
    return (
        isinstance(df, nw.DataFrame)
        or isinstance(df, nw_main.DataFrame)
        or isinstance(df, nw1.DataFrame)
    )
