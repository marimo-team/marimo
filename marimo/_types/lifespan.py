# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from collections.abc import (
    Callable,
    Mapping,
)
from contextlib import AbstractAsyncContextManager
from typing import Any, TypeVar, Union

AppType = TypeVar("AppType")

StatelessLifespan = Callable[[AppType], AbstractAsyncContextManager[None]]
StatefulLifespan = Callable[
    [AppType], AbstractAsyncContextManager[Mapping[str, Any]]
]
Lifespan = Union[StatelessLifespan[AppType], StatefulLifespan[AppType]]
