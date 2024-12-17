# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import inspect
import types
from typing import Any


def is_callable_method(obj: Any, attr: str) -> bool:
    if not hasattr(obj, attr):
        return False

    method = getattr(obj, attr)
    if inspect.isclass(obj) and not isinstance(method, (types.MethodType)):
        return False
    return callable(method)
