# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import dataclasses
import json
from asyncio import iscoroutine
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Optional, TypeVar

from starlette.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    PlainTextResponse,
    RedirectResponse,
    Response,
    StreamingResponse,
)
from starlette.routing import Mount, Router

from marimo import _loggers
from marimo._server.models.base import deep_to_camel_case

if TYPE_CHECKING:
    from starlette.requests import Request

LOGGER = _loggers.marimo_logger()

DecoratedCallable = TypeVar("DecoratedCallable", bound=Callable[..., Any])


@dataclass
class APIRouter(Router):
    def __init__(self, prefix: str = "") -> None:
        self.prefix = prefix
        super().__init__()

    def __post_init__(self) -> None:
        if self.prefix:
            assert self.prefix.startswith(
                "/"
            ), "Path prefix must start with '/'"
            assert not self.prefix.endswith(
                "/"
            ), "Path prefix must not end with '/'"

    def post(
        self, path: str
    ) -> Callable[[DecoratedCallable], DecoratedCallable]:
        """Post method that returns a JSON response"""

        def decorator(func: DecoratedCallable) -> DecoratedCallable:
            async def wrapper_func(request: Request) -> Response:
                response = await func(request=request)
                if isinstance(response, FileResponse):
                    return response
                if isinstance(response, StreamingResponse):
                    return response
                if isinstance(response, HTMLResponse):
                    return response
                if isinstance(response, PlainTextResponse):
                    return response
                if isinstance(response, RedirectResponse):
                    return response

                if dataclasses.is_dataclass(response):
                    return JSONResponse(
                        content=deep_to_camel_case(
                            dataclasses.asdict(response)
                        )
                    )

                return JSONResponse(content=json.dumps(response))

            # Set docstring of wrapper_func to the docstring of func
            wrapper_func.__doc__ = func.__doc__

            self.add_route(
                path=self.prefix + path,
                endpoint=wrapper_func,
                methods=["POST"],
            )

            return wrapper_func  # type: ignore[return-value]

        return decorator

    def get(
        self,
        path: str,
        include_in_schema: bool = True,
        name: Optional[str] = None,
    ) -> Callable[[DecoratedCallable], DecoratedCallable]:
        """Get method."""

        def decorator(func: DecoratedCallable) -> DecoratedCallable:
            async def wrapper_func(request: Request) -> Response:
                response = func(request=request)
                if iscoroutine(response):
                    response = await response
                if isinstance(response, FileResponse):
                    return response
                if isinstance(response, StreamingResponse):
                    return response
                if isinstance(response, PlainTextResponse):
                    return response
                if isinstance(response, RedirectResponse):
                    return response
                if isinstance(response, HTMLResponse):
                    return response

                if dataclasses.is_dataclass(response):
                    return JSONResponse(
                        content=deep_to_camel_case(
                            dataclasses.asdict(response)
                        )
                    )

                return response  # type: ignore[no-any-return]

            # Set docstring of wrapper_func to the docstring of func
            wrapper_func.__doc__ = func.__doc__

            self.add_route(
                path=self.prefix + path,
                endpoint=wrapper_func,
                methods=["GET"],
                include_in_schema=include_in_schema,
                name=name,
            )
            return func

        return decorator

    def delete(
        self, path: str, include_in_schema: bool = True
    ) -> Callable[[DecoratedCallable], DecoratedCallable]:
        """Delete method."""

        def decorator(func: DecoratedCallable) -> DecoratedCallable:
            self.add_route(
                path=self.prefix + path,
                endpoint=func,
                methods=["DELETE"],
                include_in_schema=include_in_schema,
            )
            return func

        return decorator

    def websocket(
        self, path: str
    ) -> Callable[[DecoratedCallable], DecoratedCallable]:
        """Websocket method."""

        def decorator(func: DecoratedCallable) -> DecoratedCallable:
            self.add_websocket_route(path=self.prefix + path, endpoint=func)
            return func

        return decorator

    def include_router(
        self, router: APIRouter, prefix: str = "", name: Optional[str] = None
    ) -> None:
        """Include another router in this one."""
        # Merge Mounts with the same path
        resolved_prefix = self.prefix + prefix
        for route in self.routes:
            if isinstance(route, Mount) and route.path == resolved_prefix:
                # NOTE: We don't merge middleware here, because it's not
                # clear what the correct behavior is.
                route.routes.extend(router.routes)
                return

        self.mount(path=resolved_prefix, app=router, name=name)
