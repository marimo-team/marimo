# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

import base64
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd


def build_data_url(mimetype: str, data: bytes) -> str:
    assert mimetype is not None
    # `data` must be base64 encoded
    str_repr = data.decode("utf-8").replace("\n", "")
    return f"data:{mimetype};base64,{str_repr}"


# Format: data:mime_type;base64,data
def from_data_uri(data: str) -> tuple[str, bytes]:
    assert isinstance(data, str)
    assert data.startswith("data:")
    mime_type, data = data.split(",", 1)
    # strip data: and ;base64
    mime_type = mime_type.split(";")[0][5:]
    return mime_type, base64.b64decode(data)


def convert_data_bytes_to_pandas_df(
    data: str, data_format: str
) -> pd.DataFrame:
    import io

    import pandas as pd

    data_bytes = from_data_uri(data)[1]

    if data_format == "csv":
        df = pd.read_csv(io.BytesIO(data_bytes))
        # Convert column names to integers if they represent integers
        df.columns = pd.Index(
            [
                int(col) if isinstance(col, str) and col.isdigit() else col
                for col in df.columns
            ]
        )
        return df
    elif data_format == "json":
        return pd.read_json(io.BytesIO(data_bytes))
    else:
        raise ValueError(f"Unsupported data_format: {data_format}")
