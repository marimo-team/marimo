# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import base64
from typing import Any, Literal, TypedDict, Union

import narwhals.stable.v1 as nw
from narwhals.typing import IntoDataFrame

import marimo._output.data.data as mo_data
from marimo import _loggers
from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins.ui._impl.tables.utils import (
    get_table_manager,
    get_table_manager_or_none,
)
from marimo._utils.data_uri import build_data_url
from marimo._utils.narwhals_utils import can_narwhalify

LOGGER = _loggers.marimo_logger()

Data = Union[dict[Any, Any], IntoDataFrame, nw.DataFrame[Any]]
_DataType = Union[dict[Any, Any], IntoDataFrame, nw.DataFrame[Any]]


class _JsonFormatDict(TypedDict):
    type: Literal["json"]


class _CsvFormatDict(TypedDict):
    type: Literal["csv"]


class _ArrowFormatDict(TypedDict):
    type: Literal["arrow"]


class _TransformResult(TypedDict):
    url: str
    format: Union[_CsvFormatDict, _JsonFormatDict, _ArrowFormatDict]


def _to_marimo_json(data: Data, **kwargs: Any) -> _TransformResult:
    """
    Custom implementation of altair.utils.data.to_json that
    returns a VirtualFile URL instead of writing to disk.
    """
    del kwargs
    data_json = _data_to_json_string(data)
    virtual_file = mo_data.json(data_json.encode("utf-8"))
    return {"url": virtual_file.url, "format": {"type": "json"}}


def _to_marimo_csv(data: Data, **kwargs: Any) -> _TransformResult:
    """
    Custom implementation of altair.utils.data.to_csv that
    returns a VirtualFile URL instead of writing to disk.
    """
    del kwargs
    data_csv = _data_to_csv_string(data)
    virtual_file = mo_data.csv(data_csv.encode("utf-8"))
    return {"url": virtual_file.url, "format": {"type": "csv"}}


def _to_marimo_arrow(data: Data, **kwargs: Any) -> _TransformResult:
    """
    Convert data to arrow format, falls back to CSV if not possible.
    """
    del kwargs
    data = _maybe_sanitize_dataframe(data)
    try:
        data_arrow = get_table_manager(data).to_arrow_ipc()
    except NotImplementedError:
        return _to_marimo_csv(data)
    except Exception as e:
        LOGGER.warning(
            f"Failed to convert data to arrow format, falling back to CSV: {e}"
        )
        return _to_marimo_csv(data)
    virtual_file = mo_data.arrow(data_arrow)
    return {"url": virtual_file.url, "format": {"type": "arrow"}}


def _to_marimo_inline_csv(data: Data, **kwargs: Any) -> _TransformResult:
    """
    Custom implementation of altair.utils.data.to_csv that
    inlines the CSV data in the URL.
    """
    del kwargs
    data_csv = _data_to_csv_string(data)
    url = build_data_url(
        mimetype="text/csv",
        data=base64.b64encode(data_csv.encode("utf-8")),
    )
    return {"url": url, "format": {"type": "csv"}}


# Copied from https://github.com/altair-viz/altair/blob/0ca83784e2455f2b84d0f6d789af2abbe8814348/altair/utils/data.py#L263C1-L288C10
def _data_to_json_string(data: _DataType) -> str:
    """Return a JSON string representation of the input data"""
    data = _maybe_sanitize_dataframe(data)

    tm = get_table_manager_or_none(data)
    if tm:
        return tm.to_json().decode("utf-8")

    raise NotImplementedError(
        "to_marimo_json only works with data expressed as a DataFrame "
        + f" or as a dict. Got {type(data)}"
    )


def _data_to_csv_string(data: _DataType) -> str:
    """Return a CSV string representation of the input data"""
    data = _maybe_sanitize_dataframe(data)
    return get_table_manager(data).to_csv_str()


def _maybe_sanitize_dataframe(data: Any) -> Any:
    """Sanitize a pandas or narwhals DataFrame for JSON serialization"""
    import altair as alt

    # First try to sanitize with sanitize_pandas_dataframe
    # because sanitize_narwhals_dataframe on pandas does not
    # produce a correct result.
    if DependencyManager.pandas.imported():
        import pandas as pd

        if isinstance(
            data, pd.DataFrame
        ) and "sanitize_pandas_dataframe" in dir(alt.utils):
            return alt.utils.sanitize_pandas_dataframe(data)  # type: ignore[attr-defined]

    # Then try to sanitize with sanitize_narwhals_dataframe
    if can_narwhalify(data) and "sanitize_narwhals_dataframe" in dir(
        alt.utils
    ):
        narwhals_data = nw.from_native(data)
        try:
            res: nw.DataFrame[Any] = alt.utils.sanitize_narwhals_dataframe(
                narwhals_data  # type: ignore[arg-type]
            )
            return res.to_native()  # type: ignore[return-value]
        except Exception as e:
            LOGGER.warning(f"Failed to sanitize narwhals dataframe: {e}")
            return data

    return data


def sanitize_nan_infs(data: Any) -> Any:
    """Sanitize NaN and Inf values in Dataframes for JSON serialization."""
    if can_narwhalify(data):
        narwhals_data = nw.from_native(data)
        for col, dtype in narwhals_data.schema.items():
            # Only numeric columns can have NaN or Inf values
            if dtype.is_numeric():
                narwhals_data = narwhals_data.with_columns(
                    nw.when(nw.col(col).is_nan() | ~nw.col(col).is_finite())
                    .then(None)
                    .otherwise(nw.col(col))
                    .name.keep()
                )
        return narwhals_data.to_native()
    return data


def register_transformers() -> None:
    """
    Register custom data transformers for Altair.

    We register a CSV transformer and a JSON transformer. These
    transformers return a VirtualFile URL instead of writing to disk,
    which is the default behavior of Altair's to_csv and to_json.

    By registering these transformers, we are able to use
    much larger datasets.
    """
    import altair as alt

    # We keep the previous options, in case the user has set them
    # we don't want to override them.

    # Default to CSV. Due to the columnar nature of CSV, it is more efficient
    # than JSON for large datasets (~80% smaller file size).
    alt.data_transformers.register("marimo", _to_marimo_csv)  # type: ignore[arg-type]
    alt.data_transformers.register("marimo_inline_csv", _to_marimo_inline_csv)  # type: ignore[arg-type]
    alt.data_transformers.register("marimo_json", _to_marimo_json)  # type: ignore[arg-type]
    alt.data_transformers.register("marimo_csv", _to_marimo_csv)  # type: ignore[arg-type]
    alt.data_transformers.register("marimo_arrow", _to_marimo_arrow)  # type: ignore[arg-type]
