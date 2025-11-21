from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from typing import TYPE_CHECKING, Any

from starlette.applications import Starlette
from starlette.responses import PlainTextResponse, Response
from starlette.testclient import TestClient

from marimo._server.asgi import (
    ASGIAppBuilder,
    DynamicDirectoryMiddleware,
    create_asgi_app,
)

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.types import ASGIApp, Message, Receive, Scope, Send
    from starlette.websockets import WebSocket

contents = """
import marimo

__generated_with = "0.0.1"
app = marimo.App()


@app.cell
def __():
    import marimo as mo
    print("Hello from placeholder")
    return mo,


if __name__ == "__main__":
    app.run()
"""


class TestASGIAppBuilder(unittest.TestCase):
    def setUp(self) -> None:
        # Create a temporary directory for the tests
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app1 = os.path.join(self.temp_dir.name, "app1.py")
        self.app2 = os.path.join(self.temp_dir.name, "app2.py")
        with open(self.app1, "w") as f:
            f.write(contents.replace("placeholder", "app1"))
        with open(self.app2, "w") as f:
            f.write(contents.replace("placeholder", "app2"))

    def tearDown(self) -> None:
        # Clean up the temporary directory
        self.temp_dir.cleanup()

    def test_create_asgi_app(self) -> None:
        builder = create_asgi_app(quiet=True, include_code=True)
        assert isinstance(builder, ASGIAppBuilder)

        builder = create_asgi_app(quiet=True, include_code=True)
        assert isinstance(builder, ASGIAppBuilder)

        builder = builder.with_app(path="/test", root=self.app1)
        app = builder.build()
        assert callable(app)

    def test_app_base(self) -> None:
        builder = create_asgi_app(quiet=True, include_code=True)
        builder = builder.with_app(path="/", root=self.app1)
        app = builder.build()
        client = TestClient(app)
        response = client.get("/")
        assert response.status_code == 200
        assert "app1.py" in response.text

    def test_app_redirect(self) -> None:
        builder = create_asgi_app(quiet=True, include_code=True)
        builder = builder.with_app(path="/test", root=self.app1)
        app = builder.build()
        client = TestClient(app)
        response = client.get("/test")
        assert response.status_code == 200, response.text
        assert "app1.py" in response.text

    def test_multiple_apps(self) -> None:
        builder = create_asgi_app(quiet=True, include_code=True)
        builder = builder.with_app(path="/app1", root=self.app1)
        builder = builder.with_app(path="/app2", root=self.app2)
        app = builder.build()
        client = TestClient(app)
        response = client.get("/app1")
        assert response.status_code == 200, response.text
        assert "app1" in response.text
        response = client.get("/app2")
        assert response.status_code == 200, response.text
        assert "app2" in response.text
        response = client.get("/")
        assert response.status_code == 404, response.text
        response = client.get("/app3")
        assert response.status_code == 404, response.text

    def test_root_doesnt_conflict_when_root_is_last(self) -> None:
        builder = create_asgi_app(quiet=True, include_code=True)
        builder = builder.with_app(path="/app1", root=self.app1)
        builder = builder.with_app(path="/", root=self.app2)
        app = builder.build()
        client = TestClient(app)
        response = client.get("/app1")
        assert response.status_code == 200, response.text
        assert "app1.py" in response.text
        response = client.get("/")
        assert response.status_code == 200, response.text
        assert "app2.py" in response.text

    def test_root_doesnt_conflict_when_root_is_first(self) -> None:
        builder = create_asgi_app(quiet=True, include_code=True)
        builder = builder.with_app(path="/", root=self.app2)
        builder = builder.with_app(path="/app1", root=self.app1)
        app = builder.build()
        client = TestClient(app)
        response = client.get("/app1")
        assert response.status_code == 200, response.text
        assert "app1.py" in response.text
        response = client.get("/")
        assert response.status_code == 200, response.text
        assert "app2.py" in response.text

    def test_can_include_code(self) -> None:
        builder = create_asgi_app(quiet=True, include_code=True)
        builder = builder.with_app(path="/app1", root=self.app1)
        app = builder.build()
        client = TestClient(app)
        response = client.get("/app1")
        assert response.status_code == 200, response.text
        assert "app1.py" in response.text

    def test_can_hit_health(self) -> None:
        builder = create_asgi_app(quiet=True, include_code=True)
        builder = builder.with_app(path="/app1", root=self.app1)
        app = builder.build()
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 404, response.text
        response = client.get("/app1/health")
        assert response.status_code == 200, response.text

    def test_mount_at_root(self) -> None:
        """Test that assets are correctly served when app is mounted at the root path."""
        builder = create_asgi_app(quiet=True, include_code=True)
        builder = builder.with_app(path="/app1", root=self.app1)
        app = builder.build()

        base_app = Starlette()
        base_app.mount("/", app)
        client = TestClient(base_app)

        # Index page
        response = client.get("/app1")
        assert response.status_code == 200, response.text
        # Index page with trailing slash
        response = client.get("/app1/")
        assert response.status_code == 200, response.text
        # Health check
        response = client.get("/app1/health")
        assert response.status_code == 200, response.text

    def test_mount_at_non_root(self) -> None:
        """Test that assets are correctly served when app is mounted at a non-root path."""
        builder = create_asgi_app(quiet=True, include_code=True)
        builder = builder.with_app(path="/app1", root=self.app1)
        app = builder.build()

        base_app = Starlette()
        base_app.mount("/marimo", app)
        client = TestClient(base_app)

        # Not at the root
        response = client.get("/app1")
        assert response.status_code == 404, response.text

        # Index page
        response = client.get("/marimo/app1")
        assert response.status_code == 200, response.text
        # Index page with trailing slash
        response = client.get("/marimo/app1/")
        assert response.status_code == 200, response.text
        # Health check
        response = client.get("/marimo/app1/health")
        assert response.status_code == 200, response.text

    def test_app_with_middleware(self):
        # Create a simple middleware
        class TestMiddleware:
            def __init__(self, app: ASGIApp):
                self.app = app

            async def __call__(
                self,
                scope: Scope,
                receive: Receive,
                send: Send,
            ) -> None:
                if scope["type"] == "http":

                    async def wrapped_send(message: Message) -> None:
                        if message["type"] == "http.response.start":
                            headers: Any = dict(message.get("headers", []))
                            headers[b"x-test-middleware"] = b"applied"
                            message["headers"] = list(headers.items())
                        await send(message)

                    await self.app(scope, receive, wrapped_send)
                else:
                    await self.app(scope, receive, send)

        builder = create_asgi_app(quiet=True, include_code=True)
        builder = builder.with_app(
            path="/app1", root=self.app1, middleware=[TestMiddleware]
        )
        app = builder.build()
        client = TestClient(app)
        response = client.get("/app1")
        assert response.status_code == 200
        assert response.headers["x-test-middleware"] == "applied"

    def test_multiple_middleware(self):
        def middleware1(app: ASGIApp) -> ASGIApp:
            async def middleware_app(
                scope: Scope, receive: Receive, send: Send
            ) -> None:
                async def wrapped_send(message: Message) -> None:
                    if message["type"] == "http.response.start":
                        headers: Any = dict(message.get("headers", []))
                        headers[b"x-middleware-1"] = b"applied"
                        message["headers"] = list(headers.items())
                    await send(message)

                await app(scope, receive, wrapped_send)

            return middleware_app

        def middleware2(app: ASGIApp) -> ASGIApp:
            async def middleware_app(
                scope: Scope, receive: Receive, send: Send
            ) -> None:
                async def wrapped_send(message: Message) -> None:
                    if message["type"] == "http.response.start":
                        headers: Any = dict(message.get("headers", []))
                        headers[b"x-middleware-2"] = b"applied"
                        message["headers"] = list(headers.items())
                    await send(message)

                await app(scope, receive, wrapped_send)

            return middleware_app

        builder = create_asgi_app(quiet=True, include_code=True)
        builder = builder.with_app(
            path="/app1", root=self.app1, middleware=[middleware1, middleware2]
        )
        app = builder.build()
        client = TestClient(app)
        response = client.get("/app1")
        assert response.status_code == 200
        assert response.headers["x-middleware-1"] == "applied"
        assert response.headers["x-middleware-2"] == "applied"

    def test_session_ttl_parameter(self):
        """Test that session_ttl parameter is passed to SessionManager."""
        builder = create_asgi_app(
            quiet=True, include_code=True, session_ttl=300
        )
        builder = builder.with_app(path="/app1", root=self.app1)
        builder.build()

        # Access the app state to verify session_ttl was set
        # We need to get the Starlette app inside the builder
        starlette_app = builder._app_cache[self.app1]
        session_manager = starlette_app.state.session_manager
        assert session_manager.ttl_seconds == 300

    def test_asset_url_parameter(self):
        """Test that asset_url parameter is passed to app state."""
        custom_asset_url = "https://my-cdn.com/assets/{version}/"
        builder = create_asgi_app(
            quiet=True, include_code=True, asset_url=custom_asset_url
        )
        app = builder.with_app(path="/app1", root=self.app1).build()

        # Check that asset_url is set on the base app
        from marimo._server.api.deps import AppStateBase

        state = AppStateBase.from_app(app)
        assert state.asset_url == custom_asset_url

        # Also check that it's set on individual mounted apps
        starlette_app = builder._app_cache[self.app1]
        assert starlette_app.state.asset_url == custom_asset_url

    def test_asset_url_none_by_default(self):
        """Test that asset_url is None when not specified."""
        builder = create_asgi_app(quiet=True, include_code=True)
        app = builder.with_app(path="/app1", root=self.app1).build()

        from marimo._server.api.deps import AppStateBase

        state = AppStateBase.from_app(app)
        assert state.asset_url is None

    def test_redirect_console_to_browser_parameter(self):
        """Test that redirect_console_to_browser parameter is passed to SessionManager."""
        builder = create_asgi_app(
            quiet=True, include_code=True, redirect_console_to_browser=True
        )
        builder = builder.with_app(path="/app1", root=self.app1)
        builder.build()

        # Access the app state to verify redirect_console_to_browser was set
        starlette_app = builder._app_cache[self.app1]
        session_manager = starlette_app.state.session_manager
        assert session_manager.redirect_console_to_browser is True

    def test_redirect_console_to_browser_defaults_to_false(self):
        """Test that redirect_console_to_browser defaults to False when not specified."""
        builder = create_asgi_app(quiet=True, include_code=True)
        builder = builder.with_app(path="/app1", root=self.app1)
        builder.build()

        # Access the app state to verify default value
        starlette_app = builder._app_cache[self.app1]
        session_manager = starlette_app.state.session_manager
        assert session_manager.redirect_console_to_browser is False


class TestDynamicDirectoryMiddleware(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for test files
        self.temp_dir = tempfile.mkdtemp()

        # Create some test files
        self.test_file = Path(self.temp_dir) / "test_app.py"
        self.test_file.write_text(contents)

        # Create nested directory structure
        nested_dir = Path(self.temp_dir) / "nested"
        nested_dir.mkdir()
        self.nested_file = nested_dir / "nested_app.py"
        self.nested_file.write_text(contents)

        # Create deeper nested structure
        deep_dir = nested_dir / "deep"
        deep_dir.mkdir()
        self.deep_file = deep_dir / "deep_app.py"
        self.deep_file.write_text("# Deep nested app")

        self.hidden_file = Path(self.temp_dir) / "_hidden.py"
        self.hidden_file.write_text(contents)

        # Create a base app that returns 404
        self.base_app = Starlette()

        async def catch_all(request: Request) -> Response:
            del request
            return PlainTextResponse("Not Found", status_code=404)

        self.base_app.add_route("/{path:path}", catch_all)

        # Create a simple app builder
        def app_builder(base_url: str, file_path: str) -> Starlette:
            del base_url
            app = Starlette()

            async def handle_assets(request: Request) -> Response:
                return PlainTextResponse(
                    f"Asset of {request.path_params['path']}"
                )

            app.add_route("/assets/{path:path}", handle_assets)

            async def handle(request: Request) -> Response:
                del request
                return PlainTextResponse(f"App from {Path(file_path).stem}")

            app.add_route("/{path:path}", handle)
            return app

        # Create the middleware
        self.app_with_middleware = DynamicDirectoryMiddleware(
            app=self.base_app,
            base_path="/apps",
            directory=self.temp_dir,
            app_builder=app_builder,
        )

        self.client = TestClient(self.app_with_middleware)

    def tearDown(self):
        # Clean up temp directory
        for root, dirs, files in os.walk(self.temp_dir, topdown=False):
            for name in files:
                os.remove(os.path.join(root, name))
            for name in dirs:
                os.rmdir(os.path.join(root, name))
        os.rmdir(self.temp_dir)

    def test_non_matching_path_passes_through(self):
        response = self.client.get("/other/path")
        assert response.status_code == 404
        assert response.text == "Not Found"

    def test_missing_file_passes_through(self):
        response = self.client.get("/apps/nonexistent")
        assert response.status_code == 404
        assert response.text == "Not Found"

    def test_hidden_file_passes_through(self):
        response = self.client.get("/apps/_hidden")
        assert response.status_code == 404
        assert response.text == "Not Found"

    def test_valid_app_path(self):
        response = self.client.get("/apps/test_app/")
        assert response.status_code == 200
        assert response.text == "App from test_app"

    def test_missing_trailing_slash_redirects(self):
        response = self.client.get("/apps/test_app", follow_redirects=False)
        assert response.status_code == 307
        assert response.headers["location"] == "/apps/test_app/"

    def test_loading_assets(self):
        # Should not work before the app is created
        response = self.client.get("/apps/test_app/assets/marimo.css")
        assert response.status_code == 404

        # First request should create the app
        response = self.client.get("/apps/test_app/")
        assert response.status_code == 200

        response = self.client.get("/apps/test_app/assets/marimo.css")
        assert response.status_code == 200
        assert response.text == "Asset of marimo.css"

    def test_websocket_path_rewriting(self):
        # Create a WebSocket test app
        def ws_app_builder(base_url: str, file_path: str) -> Starlette:
            del base_url
            app = Starlette()

            async def websocket_endpoint(websocket: WebSocket) -> None:
                await websocket.accept()
                await websocket.send_text(f"WS from {Path(file_path).stem}")
                await websocket.close()

            app.add_websocket_route("/ws", websocket_endpoint)

            async def handle(request: Request) -> Response:
                del request
                return PlainTextResponse(f"App from {Path(file_path).stem}")

            app.add_route("/", handle)
            return app

        # Create middleware with WebSocket support
        ws_middleware = DynamicDirectoryMiddleware(
            app=self.base_app,
            base_path="/apps",
            directory=self.temp_dir,
            app_builder=ws_app_builder,
        )
        ws_client = TestClient(ws_middleware)

        # First request should create the app
        response = ws_client.get("/apps/test_app/")
        assert response.status_code == 200

        with ws_client.websocket_connect("/apps/test_app/ws") as websocket:
            data = websocket.receive_text()
            assert data == "WS from test_app"

    def test_app_caching(self):
        # First request should create the app
        response1 = self.client.get("/apps/test_app/")
        assert response1.status_code == 200

        # Get the cached app
        cached_app = self.app_with_middleware._app_cache[str(self.test_file)]

        # Second request should use the same app
        response2 = self.client.get("/apps/test_app/")
        assert response2.status_code == 200

        # Verify the app is still the same instance
        assert (
            self.app_with_middleware._app_cache[str(self.test_file)]
            is cached_app
        )

    def test_dynamic_file_addition(self):
        # Add a new file after middleware creation
        new_file = Path(self.temp_dir) / "new_app.py"
        new_file.write_text("# New app")

        # Should work with the new file
        response = self.client.get("/apps/new_app/")
        assert response.status_code == 200
        assert response.text == "App from new_app"

    def test_subpath_handling(self):
        # First request should create the app
        response = self.client.get("/apps/test_app/")
        assert response.status_code == 200
        assert response.text == "App from test_app"

        # Subpath should work
        response = self.client.get("/apps/test_app/subpath")
        assert response.status_code == 200
        assert response.text == "App from test_app"

    def test_query_params_preserved_in_redirect(self):
        response = self.client.get(
            "/apps/test_app?param=value", follow_redirects=False
        )
        assert response.status_code == 307
        assert response.headers["location"] == "/apps/test_app/?param=value"

    def test_nested_file_access(self):
        response = self.client.get("/apps/nested/nested_app/")
        assert response.status_code == 200
        assert response.text == "App from nested_app"

    def test_deep_nested_file_access(self):
        response = self.client.get("/apps/nested/deep/deep_app/")
        assert response.status_code == 200
        assert response.text == "App from deep_app"

    def test_nested_file_redirect(self):
        response = self.client.get(
            "/apps/nested/nested_app", follow_redirects=False
        )
        assert response.status_code == 307
        assert response.headers["location"] == "/apps/nested/nested_app/"

    def test_nested_file_with_query_params(self):
        response = self.client.get(
            "/apps/nested/nested_app?param=value", follow_redirects=False
        )
        assert response.status_code == 307
        assert (
            response.headers["location"]
            == "/apps/nested/nested_app/?param=value"
        )

    def test_nested_file_websocket(self):
        def ws_app_builder(base_url: str, file_path: str) -> Starlette:
            del base_url
            app = Starlette()

            async def websocket_endpoint(websocket: WebSocket) -> None:
                await websocket.accept()
                await websocket.send_text(f"WS from {Path(file_path).stem}")
                await websocket.close()

            app.add_websocket_route("/ws", websocket_endpoint)

            async def handle(request: Request) -> Response:
                del request
                return PlainTextResponse(f"App from {Path(file_path).stem}")

            app.add_route("/", handle)
            return app

        ws_middleware = DynamicDirectoryMiddleware(
            app=self.base_app,
            base_path="/apps",
            directory=self.temp_dir,
            app_builder=ws_app_builder,
        )
        ws_client = TestClient(ws_middleware)

        # First request should create the app
        response = ws_client.get("/apps/nested/nested_app/")
        assert response.status_code == 200

        with ws_client.websocket_connect(
            "/apps/nested/nested_app/ws"
        ) as websocket:
            data = websocket.receive_text()
            assert data == "WS from nested_app"

    def test_nonexistent_nested_path(self):
        response = self.client.get("/apps/nested/nonexistent/")
        assert response.status_code == 404
        assert response.text == "Not Found"

    def test_validate_callback(self):
        # Create test files
        allowed_file = Path(self.temp_dir) / "allowed_app.py"
        allowed_file.write_text(contents)

        blocked_file = Path(self.temp_dir) / "blocked_app.py"
        blocked_file.write_text(contents)

        async def async_validate(app_path: str, scope: Any):
            del scope
            # Only allow apps with "allowed" in the name
            return app_path.startswith("allowed")

        middleware = DynamicDirectoryMiddleware(
            app=self.base_app,
            base_path="/apps",
            directory=self.temp_dir,
            app_builder=default_app_builder,
            validate_callback=async_validate,
        )
        client = TestClient(middleware)

        # Allowed app should work
        response = client.get("/apps/allowed_app/")
        assert response.status_code == 200

        # Blocked app should fail
        response = client.get("/apps/blocked_app/")
        assert response.status_code == 404

    def test_sync_validate_callback(self):
        # Create test files
        allowed_file = Path(self.temp_dir) / "allowed_app.py"
        allowed_file.write_text(contents)

        blocked_file = Path(self.temp_dir) / "blocked_app.py"
        blocked_file.write_text(contents)

        def sync_validate(app_path: str, scope: Any):
            del scope
            return app_path.startswith("allowed")

        middleware = DynamicDirectoryMiddleware(
            app=self.base_app,
            base_path="/apps",
            directory=self.temp_dir,
            app_builder=default_app_builder,
            validate_callback=sync_validate,
        )
        client = TestClient(middleware)

        # Allowed app should work
        response = client.get("/apps/allowed_app/")
        assert response.status_code == 200

        # Blocked app should fail
        response = client.get("/apps/blocked_app/")
        assert response.status_code == 404

    def test_validate_custom_exception(self):
        from starlette.exceptions import HTTPException

        async def async_validate(app_path: str, scope: Any):
            del app_path
            del scope
            raise HTTPException(status_code=403)

        middleware = DynamicDirectoryMiddleware(
            app=self.base_app,
            base_path="/apps",
            directory=self.temp_dir,
            app_builder=default_app_builder,
            validate_callback=async_validate,
        )

        client = TestClient(middleware)
        response = client.get("/apps/blocked_app/")
        assert response.status_code == 403
        assert response.text == "403: Forbidden"

    def test_dynamic_directory_middleware(self):
        # Create test files
        allowed_file = Path(self.temp_dir) / "my_app.py"
        allowed_file.write_text(contents)

        blocked_file = Path(self.temp_dir) / "nested/another_app.py"
        blocked_file.write_text(contents)

        class CustomMiddleware:
            def __init__(self, app: ASGIApp):
                self.app = app

            async def __call__(
                self, scope: Scope, receive: Receive, send: Send
            ) -> None:
                # Check the marimo app file as added to the scope prior.
                file = scope["marimo_app_file"]
                assert isinstance(file, str)
                assert file.endswith(str(allowed_file)) or file.endswith(
                    str(blocked_file)
                )

                if scope["type"] == "http":

                    async def wrapped_send(message: Message) -> None:
                        if message["type"] == "http.response.start":
                            headers: Any = dict(message.get("headers", []))
                            headers[b"x-custom-middleware"] = b"applied"
                            message["headers"] = list(headers.items())
                        await send(message)

                    await self.app(scope, receive, wrapped_send)
                else:
                    await self.app(scope, receive, send)

        app = (
            create_asgi_app()
            .with_dynamic_directory(
                path="/apps",
                directory=self.temp_dir,
                middleware=[CustomMiddleware],
            )
            .build()
        )

        client = TestClient(app)

        # App
        response = client.get("/apps/my_app/")
        assert response.status_code == 200
        assert response.headers["x-custom-middleware"] == "applied"

        # Nested app
        response = client.get("/apps/nested/another_app/")
        assert response.status_code == 200
        assert response.headers["x-custom-middleware"] == "applied"


def default_app_builder(base_url: str, file_path: str) -> Starlette:
    del base_url
    app = Starlette()

    async def handle(request: Request) -> Response:
        del request
        return PlainTextResponse(f"App from {Path(file_path).stem}")

    app.add_route("/{path:path}", handle)
    return app
