# Copyright 2024 Marimo. All rights reserved.
import abc
from typing import TYPE_CHECKING, List, Tuple

from marimo._server.file_router import AppFileRouter

if TYPE_CHECKING:
    from starlette.types import ASGIApp


class ASGIAppBuilder(abc.ABC):
    @abc.abstractmethod
    def with_app(self, *, path: str, root: str) -> "ASGIAppBuilder":
        pass

    @abc.abstractmethod
    def build(self) -> "ASGIApp":
        pass


def create_asgi_app(
    *,
    quiet: bool = False,
    include_code: bool = False,
) -> ASGIAppBuilder:
    """
    Public API to create an ASGI app that can serve multiple notebooks.
    This only works for application that are in Run mode.

    **Examples.**

    You can create an ASGI app, and serve the application with a
    server like `uvicorn`:

    ```python
    import uvicorn
    builder = (
        create_asgi_app()
        .with_app(path="/app", root="app.py")
        .with_app(path="/app2", root="app2.py")
        .with_app(path="/", root="home.py")
    )
    app = builder.build()

    if __name__ == "__main__":
        uvicorn.run(app, port=8000)
    ```

    Or you can further integrate it with a FastAPI app:

    ```python
    import uvicorn
    from fastapi import FastAPI
    import my_middlewares
    import my_routes

    app = FastAPI()

    builder = (
        create_asgi_app()
        .with_app(path="/app", root="app.py")
        .with_app(path="/app2", root="app2.py")
    )

    # Add middlewares
    app.add_middleware(my_middlewares.auth_middleware)

    # Add routes
    @app.get("/login")
    async def root():
        pass

    # Add the marimo app
    app.mount("/", builder.build())

    if __name__ == "__main__":
        uvicorn.run(app, port=8000)
    ```

    **Args.**

    - quiet (bool, optional): Suppress standard out
    - include_code (bool, optional): Include notebook code in the app

    **Returns.**

    - ASGIAppBuilder: A builder object to create multiple ASGI apps
    """
    from starlette.applications import Starlette
    from starlette.responses import RedirectResponse

    import marimo._server.api.lifespans as lifespans
    from marimo._config.manager import UserConfigManager
    from marimo._server.main import create_starlette_app
    from marimo._server.model import SessionMode
    from marimo._server.sessions import NoopLspServer, SessionManager
    from marimo._server.utils import initialize_asyncio

    user_config_mgr = UserConfigManager()
    base_app = Starlette()

    # We call the entrypoint `root` instead of `filename` incase we want to
    # support directories or code in the future
    class Builder(ASGIAppBuilder):
        def __init__(self) -> None:
            self._mount_configs: List[Tuple[str, str]] = []

        def with_app(self, *, path: str, root: str) -> "ASGIAppBuilder":
            self._mount_configs.append((path, root))
            return self

        def _build_app(self, path: str, root: str) -> "ASGIAppBuilder":
            session_manager = SessionManager(
                file_router=AppFileRouter.from_filename(root),
                mode=SessionMode.RUN,
                development_mode=False,
                quiet=quiet,
                include_code=include_code,
                # Currently we only support run mode,
                # which doesn't require an LSP server
                lsp_server=NoopLspServer(),
                user_config_manager=user_config_mgr,
            )
            app = create_starlette_app(
                base_url="",
                lifespan=lifespans.Lifespans(
                    [
                        # Not all lifespans are needed for run mode
                        lifespans.etc,
                        lifespans.signal_handler,
                    ]
                ),
            )
            app.state.session_manager = session_manager
            app.state.base_url = path
            app.state.config_manager = user_config_mgr

            base_app.mount(path, app)

            # If path is not empty,
            # add a redirect from /{path} to /{path}/
            # otherwise, we get a 404
            if path:
                base_app.add_route(
                    path,
                    lambda _: RedirectResponse(
                        url=f"{path}/", status_code=301
                    ),
                )

            return self

        def build(self) -> "ASGIApp":
            # First sort the mount configs by path length
            # This is to ensure that the root app is mounted last
            self._mount_configs = sorted(
                self._mount_configs, key=lambda x: -len(x[0])
            )

            for path, root in self._mount_configs:
                self._build_app(path, root)

            return base_app

    initialize_asyncio()
    return Builder()
