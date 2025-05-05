from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.types import Lifespan

from marimo._entrypoints.registry import EntryPointRegistry

MIDDLEWARE_REGISTRY = EntryPointRegistry[Middleware](
    entry_point_group="marimo.server.asgi.middleware"
)

LIFESPAN_REGISTRY = EntryPointRegistry[Lifespan[Starlette]](
    entry_point_group="marimo.server.asgi.lifespan"
)
