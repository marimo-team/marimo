# Copyright 2023 Marimo. All rights reserved.
import json
from typing import TYPE_CHECKING, Literal, TypedDict, Union

import marimo._output.data.data as mo_data

if TYPE_CHECKING:
    import pandas as pd

Data = Union[dict, "pd.DataFrame"]
_DataType = Union[dict, "pd.DataFrame"]


class _JsonFormatDict(TypedDict):
    type: Literal["json"]


class _CsvFormatDict(TypedDict):
    type: Literal["csv"]


class _ToJsonReturnUrlDict(TypedDict):
    url: str
    format: _JsonFormatDict


class _ToCsvReturnUrlDict(TypedDict):
    url: str
    format: _CsvFormatDict


def _to_marimo_json(data: Data) -> _ToJsonReturnUrlDict:
    """
    Custom implementation of altair.utils.data.to_json that
    returns a VirtualFile URL instead of writing to disk.
    """
    data_json = _data_to_json_string(data)
    virtual_file = mo_data.json(data_json.encode("utf-8"))
    return {"url": virtual_file.url, "format": {"type": "json"}}


def _to_marimo_csv(data: Data) -> _ToCsvReturnUrlDict:
    """
    Custom implementation of altair.utils.data.to_csv that
    returns a VirtualFile URL instead of writing to disk.
    """
    data_csv = _data_to_csv_string(data)
    virtual_file = mo_data.csv(data_csv.encode("utf-8"))
    return {"url": virtual_file.url, "format": {"type": "csv"}}


# Copied from https://github.com/altair-viz/altair/blob/0ca83784e2455f2b84d0f6d789af2abbe8814348/altair/utils/data.py#L263C1-L288C10
def _data_to_json_string(data: _DataType) -> str:
    """Return a JSON string representation of the input data"""
    import altair as alt  # type: ignore[import]
    import pandas as pd

    if isinstance(data, pd.DataFrame):
        sanitized = alt.utils.sanitize_dataframe(data)
        as_str = sanitized.to_json(orient="records", double_precision=15)
        assert isinstance(as_str, str)
        return as_str
    elif isinstance(data, dict):
        if "values" not in data:
            raise KeyError("values expected in data dict, but not present.")
        return json.dumps(data["values"], sort_keys=True)
    else:
        raise NotImplementedError(
            "to_marimo_json only works with data expressed as a DataFrame "
            + " or as a dict"
        )


def _data_to_csv_string(data: _DataType) -> str:
    """Return a CSV string representation of the input data"""
    import altair as alt
    import pandas as pd

    if isinstance(data, pd.DataFrame):
        sanitized = alt.utils.sanitize_dataframe(data)
        as_str = sanitized.to_csv(index=False, na_rep="null")
        assert isinstance(as_str, str)
        return as_str
    elif isinstance(data, dict):
        if "values" not in data:
            raise KeyError("values expected in data dict, but not present")
        return pd.DataFrame.from_dict(data["values"]).to_csv(index=False)
    else:
        raise NotImplementedError(
            "to_marimo_csv only works with data expressed as a DataFrame"
            + " or as a dict"
        )


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

    # Default to CSV. Due to the columnar nature of CSV, it is more efficient
    # than JSON for large datasets (~80% smaller file size).
    alt.data_transformers.register("marimo", _to_marimo_csv)
    alt.data_transformers.enable("marimo")

    alt.data_transformers.register("marimo_json", _to_marimo_json)
    alt.data_transformers.register(
        "marimo_csv",
        _to_marimo_csv,
    )
