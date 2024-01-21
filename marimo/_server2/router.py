from dataclasses import dataclass, field
from typing import Any, Callable

from starlette.responses import JSONResponse
from starlette.routing import Mount, Route
from starlette.types import ASGIApp


@dataclass
class APIRouter:
    # Prefix to append to routes
    prefix: str = ""
    routes: list[Mount | Route] = field(default_factory=list)

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

        def decorator(func: Callable[..., Any]) -> Callable[..., JSONResponse]:
            self.routes.append(
                Route(path=self.prefix + path, endpoint=func, methods=["POST"])
            )

            def wrapper(*args, **kwargs) -> JSONResponse:
                dataclass_instance = func(*args, **kwargs)
                return JSONResponse(content=dataclass_instance.asdict())

            return wrapper

        return decorator

    def get(self, path: str):
        """Get method."""

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            self.routes.append(
                Route(path=self.prefix + path, endpoint=func, methods=["GET"])
            )
            return func

        return decorator

    def mount(self, path: str, app: ASGIApp, name: str) -> None:
        self.routes.append(Mount(self.prefix + path, app=app, name=name))
