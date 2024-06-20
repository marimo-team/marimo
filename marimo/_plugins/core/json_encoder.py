# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import dataclasses
import datetime
import json
from json import JSONEncoder
from typing import Any

from marimo._dependencies.dependencies import DependencyManager


class WebComponentEncoder(JSONEncoder):
    """Custom JSON encoder for WebComponents"""

    def default(self, o: Any) -> Any:
        obj = o
        # Handle numpy objects
        if DependencyManager.has_numpy():
            import numpy as np

            dtypes = (np.datetime64, np.complexfloating)
            if isinstance(obj, dtypes):
                return str(obj)
            elif isinstance(obj, np.integer):
                return int(obj)
            elif isinstance(obj, np.floating):
                return float(obj)
            elif isinstance(obj, np.ndarray):
                if any([np.issubdtype(obj.dtype, i) for i in dtypes]):
                    return obj.astype(str).tolist()
                return str(obj.tolist())
            elif isinstance(obj, np.dtype):
                return str(obj)

        # Handle pandas objects
        if DependencyManager.has_pandas():
            import pandas as pd

            # Opinionated or known types
            if isinstance(obj, pd.DataFrame):
                return obj.to_dict("records")
            elif isinstance(obj, pd.Series):
                return obj.to_list()
            elif isinstance(obj, pd.Categorical):
                return obj.tolist()
            elif isinstance(obj, pd.CategoricalDtype):
                return str(obj)
            elif isinstance(obj, pd.Timestamp):
                return str(obj)
            elif isinstance(obj, pd.Timedelta):
                return str(obj)
            elif isinstance(obj, pd.Interval):
                return str(obj)
            elif isinstance(obj, pd.TimedeltaIndex):
                return str(obj.astype(str).tolist())

            # Catch-all for other pandas objects
            try:
                if isinstance(obj, pd.core.base.PandasObject):  # type: ignore
                    return json.loads(obj.to_json(date_format="iso"))
            except AttributeError:
                pass

        # Handle MIME objects
        if hasattr(obj, "_mime_"):
            (mimetype, data) = obj._mime_()
            return {"mimetype": mimetype, "data": data}

        # Must come after MIME objects
        if dataclasses.is_dataclass(obj):
            return dataclasses.asdict(obj)

        # Handle bytes objects
        if isinstance(obj, bytes):
            return obj.decode("utf-8")

        # Handle set
        if isinstance(obj, set):
            return list(obj)

        # Handle datetime objects
        if isinstance(obj, datetime.datetime):
            return obj.isoformat()

        # Fallthrough to default encoder
        return JSONEncoder.default(self, obj)
