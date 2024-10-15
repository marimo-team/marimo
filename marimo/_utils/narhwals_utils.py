from __future__ import annotations

from typing import Any

import narwhals.stable.v1 as nw


@nw.narwhalify
def get_dataframe_namespace(df: nw.DataFrame[Any]) -> str:
    """
    Get the namespace of the given dataframe.
    """
    return nw.get_native_namespace(df)


@nw.narwhalify
def empty_df(df: nw.DataFrame[Any]) -> nw.DataFrame[Any]:
    """
    Get an empty dataframe with the same schema as the given dataframe.
    """
    return df[[]]


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
