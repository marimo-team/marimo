# Copyright 2023 Marimo. All rights reserved.
from json import JSONEncoder
from typing import Any


class WebComponentEncoder(JSONEncoder):
    """Custom JSON encoder for WebComponents"""

    def default(self, obj: Any) -> Any:
        # Handle MIME objects
        if hasattr(obj, "_mime_"):
            (mimetype, data) = obj._mime_()
            return {"mimetype": mimetype, "data": data}
        # Fallthrough to default encoder
        return JSONEncoder.default(self, obj)
