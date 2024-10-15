from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeGuard

import narwhals.stable.v1 as nw

if TYPE_CHECKING:
    from narwhals.typing import IntoFrame


def empty_df(native_df: IntoFrame) -> IntoFrame:
    """
    Get an empty dataframe with the same schema as the given dataframe.
    """
    if can_narwhalify(native_df):
        df = nw.from_native(native_df, eager_or_interchange_only=True)
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


def can_narwhalify(obj: Any) -> TypeGuard[IntoFrame]:
    """
    Check if the given object can be narwhalified.
    """
    if obj is None:
        return False
    try:
        nw.from_native(obj)
        return True
    except TypeError:
        return False


def assert_can_narwhalify(obj: Any) -> TypeGuard[IntoFrame]:
    """
    Assert that the given object can be narwhalified.
    """
    nw.from_native(obj)
    return True
