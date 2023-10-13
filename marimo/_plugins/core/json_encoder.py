# Copyright 2023 Marimo. All rights reserved.
from json import JSONEncoder
from typing import Any

from marimo._dependencies.dependencies import DependencyManager


class WebComponentEncoder(JSONEncoder):
    """Custom JSON encoder for WebComponents"""

    def default(self, obj: Any) -> Any:
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
                return obj.tolist()

        # Handle pandas objects
        if DependencyManager.has_pandas():
            import pandas as pd

            if isinstance(obj, pd.DataFrame):
                return obj.to_dict("records")
            elif isinstance(obj, pd.Series):
                return obj.to_list()
            elif isinstance(obj, pd.Timestamp):
                return str(obj)

        # Handle MIME objects
        if hasattr(obj, "_mime_"):
            (mimetype, data) = obj._mime_()
            return {"mimetype": mimetype, "data": data}

        # Fallthrough to default encoder
        return JSONEncoder.default(self, obj)
