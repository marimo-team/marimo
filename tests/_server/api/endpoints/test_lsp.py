# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import uvicorn
from starlette.testclient import TestClient

from marimo._server.lsp import (
    BaseLspServer,
    CompositeLspServer,
    NoopLspServer,
)
from marimo._server.main import create_starlette_app
from marimo._server.models.lsp import (
    LspHealthResponse,
    LspRestartResponse,
    LspServerHealth,
)
from tests._server.mocks import (
    get_mock_session_manager,
    get_starlette_server_state_init,
    token_header,
)

if TYPE_CHECKING:
    from starlette.applications import Starlette


@pytest.fixture
def edit_app() -> Starlette:
    app = create_starlette_app(base_url="")
    session_manager = get_mock_session_manager()
    uvicorn_server = uvicorn.Server(uvicorn.Config(app))
    uvicorn_server.servers = []
    app.state.server = uvicorn_server
    get_starlette_server_state_init(session_manager=session_manager).apply(
        app.state
    )
    return app


class TestLspEndpoints:
    """Test LSP API endpoints."""

    @pytest.mark.parametrize(
        ("method", "path"),
        [
            ("get", "/api/lsp/health"),
            ("post", "/api/lsp/restart"),
        ],
    )
    def test_unauthorized(
        self, edit_app: Starlette, method: str, path: str
    ) -> None:
        client = TestClient(edit_app)
        kwargs = {"json": {}} if method == "post" else {}
        response = getattr(client, method)(path, **kwargs)
        assert response.status_code == 401

    def test_health(self, edit_app: Starlette) -> None:
        client = TestClient(edit_app)
        response = client.get("/api/lsp/health", headers=token_header())
        assert response.status_code == 200
        content = response.json()
        # NoopLspServer returns healthy with empty servers
        assert content == {"status": "healthy", "servers": []}

    @pytest.mark.parametrize(
        "json_body",
        [
            {},
            {"serverIds": ["pylsp", "copilot"]},
        ],
    )
    def test_restart(
        self, edit_app: Starlette, json_body: dict[str, Any]
    ) -> None:
        client = TestClient(edit_app)
        response = client.post(
            "/api/lsp/restart", json=json_body, headers=token_header()
        )
        assert response.status_code == 200
        content = response.json()
        # NoopLspServer returns success with empty restarted
        assert content == {"success": True, "restarted": [], "errors": {}}


class TestLspModels:
    """Test LSP model serialization."""

    def test_models(self) -> None:
        # LspServerHealth
        health = LspServerHealth(
            server_id="pylsp",
            is_running=True,
            is_responsive=True,
            has_failed=False,
            port=8080,
            last_ping_ms=5.0,
        )
        assert health.server_id == "pylsp"
        assert health.error is None

        # LspHealthResponse
        response = LspHealthResponse(status="healthy", servers=[health])
        assert response.status == "healthy"
        assert len(response.servers) == 1

        # LspRestartResponse
        restart = LspRestartResponse(
            success=True, restarted=["pylsp"], errors={"copilot": "Failed"}
        )
        assert restart.success is True
        assert restart.errors == {"copilot": "Failed"}


class TestNoopLspServer:
    """Test NoopLspServer returns safe defaults."""

    @pytest.mark.asyncio
    async def test_health_and_restart(self) -> None:
        server = NoopLspServer()

        # Health returns healthy with no servers
        health = await server.get_health()
        assert health.status == "healthy"
        assert health.servers == []

        # Restart always succeeds with no action
        for server_ids in [None, ["pylsp"]]:
            result = await server.restart(server_ids=server_ids)
            assert result.success is True
            assert result.restarted == []
            assert result.errors == {}


class TestBaseLspServer:
    """Test BaseLspServer ping, health, and restart logic."""

    @pytest.fixture
    def mock_server(self) -> BaseLspServer:
        class MockLspServer(BaseLspServer):
            id = "mock-lsp"

            def validate_requirements(self):
                return True

            def get_command(self):
                return ["echo", "mock"]

            def missing_binary_alert(self):
                return None

        return MockLspServer(port=8080)

    @pytest.mark.asyncio
    async def test_ping_not_running(self, mock_server: BaseLspServer) -> None:
        is_responsive, ping_ms = await mock_server.ping()
        assert is_responsive is False
        assert ping_ms is None

    @pytest.mark.asyncio
    async def test_get_health_not_running(
        self, mock_server: BaseLspServer
    ) -> None:
        health = await mock_server.get_health()
        assert health.status == "unhealthy"
        assert health.servers[0].is_running is False

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("server_ids", "should_restart"),
        [
            (["other-server"], False),
            (["mock-lsp"], True),
            (None, True),
        ],
    )
    async def test_restart(
        self,
        mock_server: BaseLspServer,
        server_ids: list[str] | None,
        should_restart: bool,
    ) -> None:
        mock_server.restart_server = AsyncMock(return_value=None)
        result = await mock_server.restart(server_ids=server_ids)

        assert result.success is True
        if should_restart:
            assert result.restarted == ["mock-lsp"]
            mock_server.restart_server.assert_called_once()
        else:
            assert result.restarted == []

    @pytest.mark.asyncio
    async def test_restart_with_error(
        self, mock_server: BaseLspServer
    ) -> None:
        mock_server.restart_server = AsyncMock(
            side_effect=Exception("Test error")
        )
        result = await mock_server.restart(server_ids=["mock-lsp"])
        assert result.success is False
        assert "Test error" in result.errors["mock-lsp"]

    @pytest.mark.parametrize(
        ("startup_failed", "returncode", "expected"),
        [
            (True, None, True),  # startup failed
            (False, 1, True),  # process crashed
            (False, None, False),  # no failure
        ],
    )
    def test_has_failed(
        self,
        mock_server: BaseLspServer,
        startup_failed: bool,
        returncode: int | None,
        expected: bool,
    ) -> None:
        mock_server._startup_failed = startup_failed
        if returncode is not None:
            mock_server.process = MagicMock()
            mock_server.process.returncode = returncode
        assert mock_server.has_failed() is expected


class TestCompositeLspServer:
    """Test CompositeLspServer aggregation logic."""

    @pytest.fixture
    def mock_ports(self):
        """Mock find_free_port to return incrementing ports."""
        port = [8000]

        def side_effect(_: int) -> int:
            port[0] += 1
            return port[0]

        with patch(
            "marimo._server.lsp.find_free_port", side_effect=side_effect
        ):
            yield

    @pytest.fixture
    def config_reader(self) -> MagicMock:
        reader = MagicMock()
        reader.get_config.return_value = {
            "completion": {"copilot": False},
            "language_servers": {"pylsp": {"enabled": True}},
        }
        return reader

    @pytest.mark.asyncio
    async def test_health_no_servers_enabled(
        self, mock_ports: None, config_reader: MagicMock
    ) -> None:
        del mock_ports
        config_reader.get_config.return_value = {
            "completion": {"copilot": False},
            "language_servers": {},
        }
        server = CompositeLspServer(config_reader, min_port=8000)
        health = await server.get_health()
        assert health.status == "healthy"
        assert health.servers == []

    @pytest.mark.asyncio
    async def test_restart_unknown_server(
        self, mock_ports: None, config_reader: MagicMock
    ) -> None:
        del mock_ports
        server = CompositeLspServer(config_reader, min_port=8000)
        result = await server.restart(server_ids=["unknown-server"])
        assert result.success is False
        assert "Unknown server" in result.errors["unknown-server"]

    @pytest.mark.parametrize(
        ("copilot_value", "server_name", "expected"),
        [
            (True, "copilot", True),
            ("github", "copilot", True),
            (False, "copilot", False),
            (False, "pylsp", True),  # enabled in fixture
        ],
    )
    def test_is_enabled(
        self,
        mock_ports: None,
        config_reader: MagicMock,
        copilot_value: Any,
        server_name: str,
        expected: bool,
    ) -> None:
        del mock_ports
        config_reader.get_config.return_value = {
            "completion": {"copilot": copilot_value},
            "language_servers": {"pylsp": {"enabled": True}},
        }
        server = CompositeLspServer(config_reader, min_port=8000)
        config = config_reader.get_config()
        assert server._is_enabled(config, server_name) is expected
