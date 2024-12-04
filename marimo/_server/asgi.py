# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import abc
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.responses import Response
    from starlette.types import ASGIApp, Receive, Scope, Send

LOGGER = logging.getLogger(__name__)


class ASGIAppBuilder(abc.ABC):
    """
    Class for building ASGI applications.

    Methods:
        with_app(path: str, root: str) -> ASGIAppBuilder:
            Adds a static application to the ASGI app at the specified path.

        with_dynamic_directory(path: str, directory: str) -> ASGIAppBuilder:
            Adds a dynamic directory to the ASGI app, allowing for dynamic loading of applications from the specified directory.

        build() -> ASGIApp:
            Builds and returns the final ASGI application.
    """

    @abc.abstractmethod
    def with_app(self, *, path: str, root: str) -> "ASGIAppBuilder":
        """
        Adds a static application to the ASGI app at the specified path.

        Args:
            path (str): The URL path where the application will be mounted.
            root (str): The root directory of the application.

        Returns:
            ASGIAppBuilder: The builder instance for chaining.
        """
        pass

    @abc.abstractmethod
    def with_dynamic_directory(
        self, *, path: str, directory: str
    ) -> "ASGIAppBuilder":
        """
        Adds a dynamic directory to the ASGI app, allowing for dynamic loading of applications from the specified directory.

        Args:
            path (str): The URL path where the dynamic directory will be mounted.
            directory (str): The directory containing the applications.

        Returns:
            ASGIAppBuilder: The builder instance for chaining.
        """
        pass

    @abc.abstractmethod
    def build(self) -> "ASGIApp":
        """
        Builds and returns the final ASGI application.

        Returns:
            ASGIApp: The built ASGI application.
        """
        pass


class DynamicDirectoryMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        base_path: str,
        directory: str,
        app_builder: Callable[[str, str], ASGIApp],
    ) -> None:
        self.app = app
        self.base_path = base_path.rstrip("/")
        self.directory = Path(directory)
        self.app_builder = app_builder
        self._app_cache: Dict[str, ASGIApp] = {}
        LOGGER.debug(
            f"Initialized DynamicDirectoryMiddleware with base_path={self.base_path}, "
            f"directory={self.directory} (exists={self.directory.exists()}, "
            f"is_dir={self.directory.is_dir()})"
        )

    def _redirect_response(self, scope: Scope) -> Response:
        from starlette.requests import Request
        from starlette.responses import RedirectResponse

        request = Request(scope)

        # Get the path and query string
        path = request.url.path
        query_string = request.url.query

        # Build the redirect URL with query params
        redirect_url = f"{path}/"
        if query_string:
            redirect_url = f"{redirect_url}?{query_string}"

        LOGGER.debug(f"Redirecting to: {redirect_url}")
        return RedirectResponse(url=redirect_url, status_code=307)

    def _find_matching_file(
        self, relative_path: str
    ) -> Optional[Tuple[Path, str]]:
        """Find a matching Python file in the directory structure.
        Returns tuple of (matching file, remaining path) if found, None otherwise."""
        # Try direct match first, skip if relative path has an extension
        if not Path(relative_path).suffix:
            direct_match = self.directory / f"{relative_path}.py"
            if not direct_match.name.startswith("_") and direct_match.exists():
                return (direct_match, "")

        # Try nested path by progressively checking each part
        parts = relative_path.split("/")
        for i in range(len(parts), 0, -1):
            prefix = parts[:i]
            remaining = parts[i:]

            # Try as a Python file
            potential_path = self.directory.joinpath(*prefix)
            cache_key = str(potential_path.with_suffix(".py"))
            if (
                cache_key in self._app_cache
                and not potential_path.name.startswith("_")
            ):
                return (potential_path.with_suffix(".py"), "/".join(remaining))

        return None

    async def __call__(
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        path = scope["path"]

        if scope["type"] not in ("http", "websocket"):
            LOGGER.debug(
                f"Non-HTTP/WS request type: {scope['type']}, passing through"
            )
            await self.app(scope, receive, send)
            return

        # Only handle requests starting with the base_path
        if not path.startswith(f"{self.base_path}/"):
            LOGGER.debug(
                f"Path {path} doesn't start with base_path {self.base_path}/, passing through"
            )
            await self.app(scope, receive, send)
            return

        # Extract the relative path after the base_path
        relative_path = path[len(self.base_path) + 1 :]
        if not relative_path:
            LOGGER.debug("Empty relative_path, passing through")
            await self.app(scope, receive, send)
            return

        # Remove trailing slash for file lookup
        relative_path = relative_path.rstrip("/")

        LOGGER.debug(
            f"Received dynamic request for path: {path}. Relative path: {relative_path}"
        )

        match_result = self._find_matching_file(relative_path)
        if not match_result:
            LOGGER.debug(
                f"No matching file found for {relative_path}, passing through"
            )
            await self.app(scope, receive, send)
            return

        potential_file, remaining_path = match_result
        LOGGER.debug(
            f"Found matching file: {potential_file} with remaining path: {remaining_path}"
        )

        # For HTTP requests without trailing slash, redirect only if there's no remaining path
        if (
            scope["type"] == "http"
            and not path.endswith("/")
            and not remaining_path
        ):
            LOGGER.debug(
                "Path matches file but missing trailing slash, redirecting"
            )
            response = self._redirect_response(scope)
            await response(scope, receive, send)
            return

        # Create or get cached app
        cache_key = str(potential_file)
        if cache_key not in self._app_cache:
            LOGGER.debug(f"Creating new app for {cache_key}")
            try:
                self._app_cache[cache_key] = self.app_builder(
                    cache_key, cache_key
                )
                LOGGER.debug(f"Successfully created app for {cache_key}")
            except Exception as e:
                LOGGER.exception(f"Failed to create app for {cache_key}: {e}")
                await self.app(scope, receive, send)
                return

        # Update scope to use the remaining path
        new_scope = dict(scope)
        old_path = new_scope["path"]
        new_scope["path"] = f"/{remaining_path}" if remaining_path else "/"
        LOGGER.debug(f"Updated path: {old_path} -> {new_scope['path']}")

        try:
            await self._app_cache[cache_key](new_scope, receive, send)
            LOGGER.debug(
                f"Successfully handled {scope['type']} request for {cache_key}"
            )
        except Exception as e:
            LOGGER.exception(
                f"Error handling {scope['type']} request for {cache_key}: {e}"
            )
            # If the app fails, fall back to the main app
            await self.app(scope, receive, send)


def create_asgi_app(
    *,
    quiet: bool = False,
    include_code: bool = False,
    token: Optional[str] = None,
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

    You may also want to dynamically load notebooks from a directory. To do
    this, use the `with_dynamic_directory` method. This is useful if the
    contents of the directory change often without requiring a server restart.

    ```python
    import uvicorn

    builder = create_asgi_app().with_dynamic_directory(
        path="/notebooks", directory="./notebooks"
    )
    app = builder.build()

    if __name__ == "__main__":
        uvicorn.run(app, port=8000)
    ```

    **Args.**

    - quiet (bool, optional): Suppress standard out
    - include_code (bool, optional): Include notebook code in the app
    - token (str, optional): Auth token to use for the app.
        If not provided, an empty token is used.

    **Returns.**

    - ASGIAppBuilder: A builder object to create multiple ASGI apps
    """
    from starlette.applications import Starlette
    from starlette.responses import RedirectResponse

    import marimo._server.api.lifespans as lifespans
    from marimo._config.manager import UserConfigManager
    from marimo._server.file_router import AppFileRouter
    from marimo._server.main import create_starlette_app
    from marimo._server.model import SessionMode
    from marimo._server.sessions import NoopLspServer, SessionManager
    from marimo._server.tokens import AuthToken
    from marimo._server.utils import initialize_asyncio
    from marimo._utils.marimo_path import MarimoPath

    user_config_mgr = UserConfigManager()
    base_app = Starlette()

    # Default to an empty token
    # If a user is using the create_asgi_app API,
    # they likely want to provide their own authN/authZ
    if not token:
        auth_token = AuthToken("")
    else:
        auth_token = AuthToken(token)

    # We call the entrypoint `root` instead of `filename` incase we want to
    # support directories or code in the future
    class Builder(ASGIAppBuilder):
        def __init__(self) -> None:
            self._mount_configs: List[Tuple[str, str]] = []
            self._dynamic_directory_configs: List[Tuple[str, str]] = []
            self._app_cache: Dict[str, ASGIApp] = {}

        def with_app(self, *, path: str, root: str) -> "ASGIAppBuilder":
            self._mount_configs.append((path, root))
            return self

        def with_dynamic_directory(
            self, *, path: str, directory: str
        ) -> "ASGIAppBuilder":
            self._dynamic_directory_configs.append((path, directory))
            return self

        @staticmethod
        def _create_app_for_file(base_url: str, file_path: str) -> ASGIApp:
            session_manager = SessionManager(
                file_router=AppFileRouter.from_filename(MarimoPath(file_path)),
                mode=SessionMode.RUN,
                development_mode=False,
                quiet=quiet,
                include_code=include_code,
                # Currently we only support run mode,
                # which doesn't require an LSP server
                lsp_server=NoopLspServer(),
                user_config_manager=user_config_mgr,
                # We don't pass any CLI args for now
                # since we don't want to read arbitrary args and apply them
                # to each application
                cli_args={},
                auth_token=auth_token,
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
                enable_auth=not AuthToken.is_empty(auth_token),
                allow_origins=("*",),
            )
            app.state.session_manager = session_manager
            app.state.base_url = base_url
            app.state.config_manager = user_config_mgr
            return app

        def build(self) -> "ASGIApp":
            # Handle individual app mounts first
            # Sort to ensure the root app is mounted last
            self._mount_configs = sorted(
                self._mount_configs, key=lambda x: -len(x[0])
            )

            def create_redirect_to_slash(
                base_url: str,
            ) -> Callable[[Request], Response]:
                redirect_path = f"{base_url}/"
                return lambda _: RedirectResponse(
                    url=redirect_path, status_code=301
                )

            for path, root in self._mount_configs:
                if root not in self._app_cache:
                    self._app_cache[root] = self._create_app_for_file(
                        base_url=path, file_path=root
                    )
                base_app.mount(path, self._app_cache[root])

                # If path is not empty,
                # add a redirect from /{path} to /{path}/
                # otherwise, we get a 404
                if path and not path.endswith("/"):
                    base_app.add_route(
                        path,
                        create_redirect_to_slash(path),
                    )

            # Add dynamic directory middleware for each directory config
            app: ASGIApp = base_app
            for path, directory in self._dynamic_directory_configs:
                app = DynamicDirectoryMiddleware(
                    app=app,
                    base_path=path,
                    directory=directory,
                    app_builder=self._create_app_for_file,
                )

            return app

    initialize_asyncio()
    return Builder()
