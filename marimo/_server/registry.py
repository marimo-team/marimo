# Copyright 2025 Marimo. All rights reserved.
from typing import TYPE_CHECKING

from marimo._entrypoints.registry import EntryPointRegistry

if TYPE_CHECKING:
    from starlette.applications import Starlette
    from starlette.middleware import Middleware
    from starlette.types import Lifespan


MIDDLEWARE_REGISTRY: EntryPointRegistry["Middleware"] = EntryPointRegistry(
    entry_point_group="marimo.server.asgi.middleware"
)

LIFESPAN_REGISTRY: EntryPointRegistry["Lifespan[Starlette]"] = (
    EntryPointRegistry(entry_point_group="marimo.server.asgi.lifespan")
)
