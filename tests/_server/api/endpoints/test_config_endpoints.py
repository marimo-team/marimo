# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import Mock, patch

import pytest

from marimo._config.manager import EnvVarReader, MarimoConfigManager
from marimo._runtime.commands import UpdateUserConfigCommand
from marimo._sql.sql import get_default_result_limit
from tests._server.conftest import (
    get_user_config_manager,
)
from tests._server.mocks import get_session_manager, token_header, with_session

if TYPE_CHECKING:
    from pathlib import Path

    from starlette.testclient import TestClient

    from tests.conftest import MockedKernel


SESSION_ID = "session-123"
HEADERS = {
    "Marimo-Session-Id": SESSION_ID,
    **token_header("fake-token"),
}


def test_save_user_config_no_session(client: TestClient) -> None:
    user_config_manager = get_user_config_manager(client)
    response = client.post(
        "/api/kernel/save_user_config",
        headers=HEADERS,
        json={
            "config": user_config_manager.get_config().to_dict(),
        },
    )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/json"
    assert "success" in response.json()


@pytest.mark.parametrize("override", [None, 60])
@pytest.mark.parametrize("edit_sql", [False, True])
def test_save_user_config_keeps_higher_priority_settings(
    client: TestClient,
    mocked_kernel: MockedKernel,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    override: int | None,
    edit_sql: bool,
) -> None:
    store = get_user_config_manager(client).user_config_mgr
    config_path = tmp_path / "marimo.toml"
    config_path.write_text("[runtime]\nsql_default_limit = 25\n")
    monkeypatch.setattr(store, "get_config_path", lambda: str(config_path))
    monkeypatch.delenv("MARIMO_SQL_DEFAULT_LIMIT", raising=False)
    monkeypatch.setenv("MARIMO_RUNTIME_SQL_DEFAULT_LIMIT", "45")
    manager = MarimoConfigManager(store, EnvVarReader())
    if override is not None:
        manager = manager.with_overrides(
            {"runtime": {"sql_default_limit": override}}
        )
    resolved = manager.get_config_with_sources(hide_secrets=False)
    mocked_kernel.k.user_config = resolved.config
    mocked_kernel.k.config_overrides = set(resolved.override_paths)
    session = Mock(config_manager=manager)

    def update_kernel(
        command: UpdateUserConfigCommand, **_kwargs: object
    ) -> None:
        expected_paths = (("save", "autosave_delay"),)
        if edit_sql:
            expected_paths += (("runtime", "sql_default_limit"),)
        assert command.edited_paths == expected_paths
        mocked_kernel.k.set_user_config(command)

    session.put_control_request.side_effect = update_kernel
    with (
        patch(
            "marimo._server.api.endpoints.config.AppState.get_current_session",
            return_value=session,
        ),
        patch(
            "marimo._server.api.endpoints.config.enforce_consumer_capability"
        ),
    ):
        response = client.post(
            "/api/kernel/save_user_config",
            headers=HEADERS,
            json={
                "config": {
                    "save": {"autosave_delay": 2000},
                    **(
                        {"runtime": {"sql_default_limit": 30}}
                        if edit_sql
                        else {}
                    ),
                }
            },
        )

    assert response.status_code == 200, response.text
    session.put_control_request.assert_called_once()
    assert mocked_kernel.k.user_config["save"]["autosave_delay"] == 2000
    assert get_default_result_limit() == (
        override if override is not None else 45
    )
    assert mocked_kernel.k.config_overrides == set(resolved.override_paths)


@with_session(SESSION_ID)
def test_save_user_config_with_session(client: TestClient) -> None:
    user_config_manager = get_user_config_manager(client)
    response = client.post(
        "/api/kernel/save_user_config",
        headers=HEADERS,
        json={
            "config": user_config_manager.get_config().to_dict(),
        },
    )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/json"
    assert "success" in response.json()


@with_session(SESSION_ID)
def test_save_user_config_with_partial_config(client: TestClient) -> None:
    """
    Test that save_user_config endpoint works correctly with partial config

    This is a regression test for the KeyError: 'output_max_bytes' bug.
    Before the fix, sending partial config would cause runtime errors when
    the kernel tried to access missing config fields.
    """
    # Create a partial config that's missing required runtime fields
    partial_config = {
        "display": {
            "theme": "light",
        },
    }

    response = client.post(
        "/api/kernel/save_user_config",
        headers=HEADERS,
        json={
            "config": partial_config,
        },
    )

    # Verify the endpoint succeeds
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/json"
    assert "success" in response.json()


@with_session(SESSION_ID)
def test_save_user_config_denied_capability_does_not_write(
    client: TestClient,
) -> None:
    """A capability-denied request must not touch the config on disk.

    Regression: enforcement used to run after save_config, so a read-only
    connection could persist the config before receiving its 403.
    """
    from unittest.mock import patch

    from marimo._utils.http import HTTPException

    config_manager = get_user_config_manager(client)

    with (
        patch(
            "marimo._server.api.endpoints.config.enforce_consumer_capability",
            side_effect=HTTPException(status_code=403, detail="read-only"),
        ),
        patch.object(config_manager, "save_config") as save_config,
    ):
        response = client.post(
            "/api/kernel/save_user_config",
            headers=HEADERS,
            json={"config": {"display": {"theme": "dark"}}},
        )

    assert response.status_code == 403, response.text
    save_config.assert_not_called()


def test_save_user_config_starts_lsp_when_ty_enabled(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    called = False

    async def mock_start_lsp_server() -> None:
        nonlocal called
        called = True

    session_manager = get_session_manager(client)
    monkeypatch.setattr(
        session_manager, "start_lsp_server", mock_start_lsp_server
    )

    response = client.post(
        "/api/kernel/save_user_config",
        headers=HEADERS,
        json={
            "config": {
                "completion": {"copilot": False},
                "language_servers": {"ty": {"enabled": True}},
            },
        },
    )

    assert response.status_code == 200, response.text
    assert called is True
