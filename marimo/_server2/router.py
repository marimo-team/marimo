from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Optional

from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, Response
from starlette.routing import Mount, Router
from starlette.websockets import WebSocket

from marimo import _loggers
from marimo._server2.models.base import deep_to_camel_case

LOGGER = _loggers.marimo_logger()


@dataclass
class APIRouter(Router):
    # Prefix to append to routes
    prefix: str = ""

    def __init__(self) -> None:
        super().__init__()

    def __post_init__(self) -> None:
        if self.prefix:
            assert self.prefix.startswith(
                "/"
            ), "Path prefix must start with '/'"
            assert not self.prefix.endswith(
                "/"
            ), "Path prefix must not end with '/'"

    def post(self, path: str):
        """Post method that returns a JSON response"""

        def decorator(func: Callable[..., Awaitable[Response]]) -> None:
            async def wrapper_func(request: Request) -> Response:
                response = await func(request=request)
                if isinstance(response, FileResponse):
                    return response

                if dataclasses.is_dataclass(response):
                    return JSONResponse(
                        content=deep_to_camel_case(
                            dataclasses.asdict(response)
                        )
                    )

                return JSONResponse(content=json.dumps(response))

            self.add_route(
                path=self.prefix + path,
                endpoint=wrapper_func,
                methods=["POST"],
            )

            return

        return decorator

    def get(self, path: str):
        """Get method."""

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            self.add_route(
                path=self.prefix + path, endpoint=func, methods=["GET"]
            )
            return func

        return decorator

    def websocket(self, path: str):
        """Websocket method."""

        def decorator(func: Callable[[WebSocket], Awaitable[None]]) -> None:
            self.add_websocket_route(path=self.prefix + path, endpoint=func)
            return

        return decorator

    def include_router(
        self, router: APIRouter, prefix: str = "", name: Optional[str] = None
    ):
        """Include another router in this one."""
        # Merge Mounts with the same path
        for route in self.routes:
            if isinstance(route, Mount) and route.path == prefix:
                # NOTE: We don't merge middleware here, because it's not
                # clear what the correct behavior is.
                route.routes.extend(router.routes)
                return

        self.mount(path=prefix, app=router, name=name)
