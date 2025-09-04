# Copyright 2024 Marimo. All rights reserved.
"""Msgspec encoder with custom type support for marimo."""

from __future__ import annotations

from typing import Any

import msgspec
import msgspec.json

from marimo._dependencies.dependencies import DependencyManager


def enc_hook(obj: Any) -> Any:
    """Custom encoding hook for marimo types."""

    if isinstance(obj, range):
        return list(obj)

    if isinstance(obj, complex):
        return str(obj)

    if hasattr(obj, "_mime_"):
        mimetype, data = obj._mime_()
        return {"mimetype": mimetype, "data": data}

    if DependencyManager.numpy.imported():
        import numpy as np

        if isinstance(obj, (np.datetime64, np.complexfloating)):
            return str(obj)
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            if any(
                np.issubdtype(obj.dtype, dtype)
                for dtype in (np.datetime64, np.complexfloating)
            ):
                return obj.astype(str).tolist()
            return obj.tolist()
        if isinstance(obj, np.dtype):
            return str(obj)

    if DependencyManager.pandas.imported():
        import pandas as pd

        if isinstance(obj, pd.DataFrame):
            return obj.to_dict("records")
        if isinstance(obj, pd.Series):
            return obj.to_list()
        if isinstance(obj, pd.Categorical):
            return obj.tolist()
        if isinstance(
            obj,
            (pd.CategoricalDtype, pd.Timestamp, pd.Timedelta, pd.Interval),
        ):
            return str(obj)
        if isinstance(obj, pd.TimedeltaIndex):
            return obj.astype(str).tolist()

        # Catch-all for other pandas objects
        try:
            if isinstance(obj, pd.core.base.PandasObject):  # type: ignore
                import json

                return json.loads(obj.to_json(date_format="iso"))
        except AttributeError:
            pass

    if DependencyManager.polars.imported():
        import polars as pl

        if isinstance(obj, pl.DataFrame):
            return obj.to_dict()

        if isinstance(obj, pl.Series):
            return obj.to_list()

    raise NotImplementedError(f"Objects of type {type(obj)} are not supported")


_encoder = msgspec.json.Encoder(enc_hook=enc_hook, decimal_format="number")


def encode_json_bytes(obj: Any) -> bytes:
    """
    Encode an object as JSON and return the result as bytes.
    """
    return _encoder.encode(obj)


def encode_json_str(obj: Any) -> str:
    """
    Encode an object as JSON and return the result as a UTF-8 string.
    """
    return _encoder.encode(obj).decode("utf-8")


def asdict(obj: msgspec.Struct) -> dict[str, Any]:
    """
    Convert a msgspec.Struct into a dict of builtin Python types.

    Uses `msgspec.to_builtins` with `enc_hook` to handle unsupported values.
    """
    return msgspec.to_builtins(obj, enc_hook=enc_hook)  # type: ignore[no-any-return]
