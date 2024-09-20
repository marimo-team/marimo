# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import dataclasses
import datetime
import json
from enum import Enum
from json import JSONEncoder
from typing import Any
from uuid import UUID

from marimo._dependencies.dependencies import DependencyManager


class WebComponentEncoder(JSONEncoder):
    @staticmethod
    def json_dumps(o: Any) -> Any:
        """Serialize an object to JSON."""
        return json.dumps(o, cls=WebComponentEncoder)

    def default(self, o: Any) -> Any:
        """Override default method to handle additional types."""
        return self._convert_to_json(o)

    def _convert_to_json(self, o: Any) -> Any:
        """Convert various types to JSON serializable format."""
        # Primitives (most common case first for performance)
        if isinstance(o, (str, int, float, bool, type(None))):
            return o

        # Handle bytes objects
        if isinstance(o, bytes):
            return o.decode("utf-8")

        # Handle datetime objects
        if isinstance(o, (datetime.datetime, datetime.date, datetime.time)):
            return o.isoformat()

        # Handle UUID
        if isinstance(o, UUID):
            return str(o)

        # Handle enum
        if isinstance(o, Enum):
            return o.name

        # Handle complex numbers
        if isinstance(o, complex):
            return str(o)

        # Handle iterable objects
        if isinstance(o, (set, frozenset)):
            return list(o)

        # If handled by default encoder
        if isinstance(o, (dict, list)):
            return o

        # Handle MIME objects
        if hasattr(o, "_mime_"):
            mimetype, data = o._mime_()
            return {"mimetype": mimetype, "data": data}

        # Handle dataclasses
        # Must come after MIME objects
        if dataclasses.is_dataclass(o):
            # We cannot use asdict since we need to recursively encode
            # the values
            return {
                field.name: self._convert_to_json(getattr(o, field.name))
                for field in dataclasses.fields(o)
            }

        # Handle numpy objects
        if DependencyManager.numpy.imported():
            import numpy as np

            if isinstance(o, (np.datetime64, np.complexfloating)):
                return str(o)
            if isinstance(o, np.integer):
                return int(o)
            if isinstance(o, np.floating):
                return float(o)
            if isinstance(o, np.ndarray):
                if any(
                    np.issubdtype(o.dtype, dtype)
                    for dtype in (np.datetime64, np.complexfloating)
                ):
                    return o.astype(str).tolist()
                return o.tolist()
            if isinstance(o, np.dtype):
                return str(o)

        # Handle pandas objects
        if DependencyManager.pandas.imported():
            import pandas as pd

            if isinstance(o, pd.DataFrame):
                return o.to_dict("records")
            if isinstance(o, pd.Series):
                return o.to_list()
            if isinstance(o, pd.Categorical):
                return o.tolist()
            if isinstance(
                o,
                (pd.CategoricalDtype, pd.Timestamp, pd.Timedelta, pd.Interval),
            ):
                return str(o)
            if isinstance(o, pd.TimedeltaIndex):
                return o.astype(str).tolist()

            # Catch-all for other pandas objects
            try:
                if isinstance(o, pd.core.base.PandasObject):  # type: ignore
                    return json.loads(o.to_json(date_format="iso"))
            except AttributeError:
                pass

        # Handle named tuples
        if isinstance(o, tuple) and hasattr(o, "_fields"):
            return {
                field: self._convert_to_json(getattr(o, field))
                for field in o._fields  # type: ignore
            }

        # Handle objects with __slots__
        if hasattr(o, "__slots__"):
            return {
                slot: self._convert_to_json(getattr(o, slot))
                for slot in o.__slots__  # type: ignore
                if hasattr(o, slot)
            }

        # Handle custom objects with __dict__
        if hasattr(o, "__dict__"):
            return {
                key: self._convert_to_json(value)
                for key, value in o.__dict__.items()
            }
        # Fallthrough to default encoder
        return JSONEncoder.default(self, o)
