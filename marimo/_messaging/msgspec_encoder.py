# Copyright 2026 Marimo. All rights reserved.
"""Msgspec encoder with custom type support for marimo."""

from __future__ import annotations

import collections
import datetime
import decimal
import fractions
import uuid
from math import isnan
from pathlib import PurePath
from typing import Any

import msgspec
import msgspec.json

from marimo import _loggers
from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins.core.media import io_to_data_url

LOGGER = _loggers.marimo_logger()


def enc_hook(obj: Any) -> Any:
    """Custom encoding hook for marimo types."""

    if hasattr(obj, "_marimo_serialize_"):
        return obj._marimo_serialize_()

    if hasattr(obj, "_mime_"):
        mimetype, data = obj._mime_()
        return {"mimetype": mimetype, "data": data}

    if isinstance(obj, range):
        return list(obj)

    if isinstance(
        obj,
        (complex, fractions.Fraction, decimal.Decimal, PurePath, uuid.UUID),
    ):
        return str(obj)

    if DependencyManager.numpy.imported():
        import numpy as np

        if isinstance(
            obj, (np.datetime64, np.timedelta64, np.complexfloating)
        ):
            return str(obj)
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.bool_):
            return bool(obj)
        if isinstance(obj, (np.bytes_, np.str_)):
            return str(obj)
        if isinstance(obj, np.ndarray):
            if any(
                np.issubdtype(obj.dtype, dtype)
                for dtype in (
                    np.datetime64,
                    np.timedelta64,
                    np.complexfloating,
                )
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
            (
                pd.CategoricalDtype,
                pd.Timestamp,
                pd.Timedelta,
                pd.Interval,
                pd.Period,
            ),
        ):
            return str(obj)
        if obj is pd.NaT:
            return str(obj)
        if isinstance(
            obj,
            (
                pd.TimedeltaIndex,
                pd.DatetimeIndex,
                pd.IntervalIndex,
                pd.PeriodIndex,
            ),
        ):
            return obj.astype(str).tolist()
        if isinstance(obj, pd.MultiIndex):
            return obj.to_list()
        if isinstance(obj, pd.Index):
            return obj.to_list()

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
        if isinstance(obj, pl.LazyFrame):
            return obj.collect().to_dict()
        if isinstance(obj, pl.Series):
            return obj.to_list()

        # Handle Polars data types
        if hasattr(pl, "datatypes") and hasattr(obj, "__class__"):
            # Check if it's a Polars data type
            if hasattr(pl.datatypes, "DataType") and isinstance(
                obj, pl.datatypes.DataType
            ):
                return str(obj)

    # Handle Pillow images
    if DependencyManager.pillow.imported():
        try:
            from PIL import Image

            if isinstance(obj, Image.Image):
                return io_to_data_url(obj, "image/png")
        except Exception:
            LOGGER.debug("Unable to convert image to data URL", exc_info=True)

    # Handle Matplotlib figures
    if DependencyManager.matplotlib.imported():
        try:
            import matplotlib.figure
            from matplotlib.axes import Axes

            from marimo._output.formatting import as_html
            from marimo._plugins.stateless.flex import vstack

            if isinstance(obj, matplotlib.figure.Figure):
                html = as_html(vstack([str(obj), obj]))
                mimetype, data = html._mime_()

            if isinstance(obj, Axes):
                html = as_html(vstack([str(obj), obj]))
                mimetype, data = html._mime_()
                return {"mimetype": mimetype, "data": data}
        except Exception:
            LOGGER.debug(
                "Error converting matplotlib figures to HTML",
                exc_info=True,
            )

    # Handle objects with __slots__
    slots = getattr(obj, "__slots__", None)
    if slots is not None:
        try:
            slots = iter(slots)
        except TypeError:
            pass  # Fall through to __dict__ handling
        else:
            # Convert to dict using msgspec.to_builtins for proper handling
            result = {}
            for slot in slots:
                if hasattr(obj, slot):
                    attr_value = getattr(obj, slot)
                    # Use msgspec.to_builtins which properly handles nested structures
                    result[slot] = msgspec.to_builtins(
                        attr_value, enc_hook=enc_hook
                    )
            return result

    # Handle custom objects with `__dict__`
    if hasattr(obj, "__dict__"):
        # Convert the __dict__ using msgspec.to_builtins for proper handling
        return msgspec.to_builtins(obj.__dict__, enc_hook=enc_hook)

    # Handle collections types
    if isinstance(obj, (list, tuple, set, frozenset)):
        return list([enc_hook(item) for item in obj])

    if isinstance(obj, collections.deque):
        return list([enc_hook(item) for item in obj])

    # Handle dict and dict-like types
    if isinstance(
        obj,
        (
            dict,
            collections.defaultdict,
            collections.OrderedDict,
            collections.Counter,
        ),
    ):
        return {enc_hook(k): enc_hook(v) for k, v in obj.items()}

    # Handle float('inf'), float('nan'), float('-inf')
    if isinstance(obj, float):
        if obj == float("inf"):
            return "Infinity"
        if obj == float("-inf"):
            return "-Infinity"
        if isnan(obj):
            return "NaN"
        return obj

    # Handle bytes objects
    if isinstance(obj, memoryview):
        obj = obj.tobytes()

    if isinstance(obj, bytes):
        try:
            return obj.decode("utf-8")
        except UnicodeDecodeError:
            # Fallback to latin1
            return obj.decode("latin1")

    # Handle primitive types
    if isinstance(obj, (int, str, bool)):
        return obj

    # Handle datetime types
    if isinstance(
        obj,
        (datetime.datetime, datetime.timedelta, datetime.date, datetime.time),
    ):
        return str(obj)

    # Handle None
    if obj is None:
        return None

    return repr(obj)


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
