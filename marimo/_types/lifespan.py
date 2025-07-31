# Copyright 2025 Marimo. All rights reserved.
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
