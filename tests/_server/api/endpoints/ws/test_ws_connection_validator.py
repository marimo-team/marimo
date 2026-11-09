# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from unittest.mock import MagicMock

from marimo._config.config_schema import MarimoConfig
from marimo._server.api.endpoints.ws.ws_connection_validator import (
    ConnectionParams,
    ConnectionRejection,
    parse_connection_params,
)
from marimo._server.codes import WebSocketCloseReason, WebSocketCodes


def _app_state(
    query: dict[str, str] | None = None,
    unique_file_key: str | None = "test.py",
) -> MagicMock:
    query = query or {}
    config: MarimoConfig = MarimoConfig.from_dict(
        {"runtime": {"auto_instantiate": True}}
    )
    app_state = MagicMock()
    app_state.query_params.side_effect = query.get
    workspace = app_state.session_manager.workspace
    workspace.get_unique_file_key.return_value = unique_file_key
    manager = app_state.config_manager_at_file.return_value
    manager.get_config.return_value = config
    return app_state


def test_missing_session_id_is_rejected() -> None:
    result = parse_connection_params(_app_state())
    assert result == ConnectionRejection(
        WebSocketCodes.NORMAL_CLOSE, WebSocketCloseReason.NO_SESSION_ID
    )


def test_missing_file_key_is_rejected() -> None:
    result = parse_connection_params(
        _app_state(query={"session_id": "123"}, unique_file_key=None)
    )
    assert result == ConnectionRejection(
        WebSocketCodes.NORMAL_CLOSE, WebSocketCloseReason.NO_FILE_KEY
    )


def test_extracts_params() -> None:
    result = parse_connection_params(
        _app_state(query={"session_id": "123", "kiosk": "true"})
    )
    assert result == ConnectionParams(
        session_id="123",
        file_key="test.py",
        kiosk=True,
        auto_instantiate=True,
    )


def test_file_query_param_wins_over_unique_file_key() -> None:
    result = parse_connection_params(
        _app_state(query={"session_id": "123", "file": "other.py"})
    )
    assert isinstance(result, ConnectionParams)
    assert result.file_key == "other.py"
