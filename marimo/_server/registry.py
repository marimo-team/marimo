from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from starlette.applications import Starlette  # noqa: TC004
    from starlette.middleware import Middleware  # noqa: TC004
    from starlette.types import Lifespan  # noqa: TC004

from marimo._entrypoints.registry import EntryPointRegistry

MIDDLEWARE_REGISTRY = EntryPointRegistry[Middleware](
    entry_point_group="marimo.server.asgi.middleware"
)

LIFESPAN_REGISTRY = EntryPointRegistry[Lifespan[Starlette]](
    entry_point_group="marimo.server.asgi.lifespan"
)
