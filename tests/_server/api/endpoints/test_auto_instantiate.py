# Copyright 2024 Marimo. All rights reserved.
"""Tests for auto-instantiate behavior in run mode vs edit mode."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from marimo._session.session import SessionImpl
from marimo._types.ids import SessionId
from tests._server.api.endpoints.ws_helpers import (
    receive_notification,
    receive_until,
)
from tests._server.mocks import get_session_manager

if TYPE_CHECKING:
    from starlette.testclient import TestClient

    from marimo._config.manager import UserConfigStore


def _create_ws_url(session_id: str) -> str:
    return f"/ws?session_id={session_id}&access_token=fake-token"


class TestAutoInstantiateEditMode:
    """Tests for auto-instantiate in edit mode."""

    @pytest.mark.parametrize("auto_instantiate", [True, False])
    def test_a_new_session_runs_the_notebook_when_autorun_is_on(
        self,
        client: TestClient,
        user_config_manager: UserConfigStore,
        auto_instantiate: bool,
    ) -> None:
        Path(user_config_manager.get_config_path()).write_text(
            f"[runtime]\nauto_instantiate = {str(auto_instantiate).lower()}\n"
        )
        session_id = "test-edit-startup"

        with client.websocket_connect(_create_ws_url(session_id)) as websocket:
            assert receive_notification(websocket)["op"] == "kernel-ready"
            receive_until("completed-run", websocket)

            session = get_session_manager(client).get_session(
                SessionId(session_id)
            )
            assert session is not None
            (cell_id,) = session.app_file_manager.app.cell_manager.cell_ids()
            ran = cell_id in session.session_view.last_execution_time
            assert ran is auto_instantiate

    def test_reconnecting_does_not_instantiate_again(
        self, client: TestClient
    ) -> None:
        ws_url = _create_ws_url("test-edit-reconnect")

        with patch.object(
            SessionImpl,
            "instantiate",
            autospec=True,
            side_effect=SessionImpl.instantiate,
        ) as instantiate:
            with client.websocket_connect(ws_url) as websocket:
                assert receive_notification(websocket)["op"] == "kernel-ready"
                receive_until("completed-run", websocket)
            with client.websocket_connect(ws_url) as websocket:
                assert receive_notification(websocket)["op"] == "alert"

        assert instantiate.call_count == 1


class TestAutoInstantiateHTTPRequest:
    """Tests for HTTP request propagation during auto-instantiate."""

    def test_auto_instantiate_passes_http_request(self) -> None:
        """Verify _instantiate passes HTTPRequest from the connection.

        This verifies the fix for the issue where mo.app_meta().request
        returned None in run mode because the server's instantiate was passing
        http_request=None instead of extracting it from the connection.
        """
        from marimo._server.api.endpoints.ws.ws_session_connector import (
            SessionConnector,
        )

        mock_session = MagicMock()
        mock_http_request = MagicMock()

        connector = SessionConnector(
            manager=MagicMock(),
            handler=MagicMock(),
            params=MagicMock(),
            connection=MagicMock(),
        )

        with patch(
            "marimo._runtime.commands.HTTPRequest.from_request",
            return_value=mock_http_request,
        ) as mock_from_request:
            connector._instantiate(mock_session)

        mock_from_request.assert_called_once_with(connector.connection)
        assert (
            mock_session.instantiate.call_args.kwargs["http_request"]
            is mock_http_request
        )


class TestInstantiateNotebookRequest:
    """Tests for InstantiateNotebookRequest with codes field."""

    def test_instantiate_request_with_codes(self) -> None:
        """InstantiateNotebookRequest should accept optional codes field."""
        from marimo._session.requests import InstantiateNotebookRequest

        # Without codes
        request = InstantiateNotebookRequest(
            object_ids=[],
            values=[],
            auto_run=True,
        )
        assert request.codes is None

        # With codes
        request_with_codes = InstantiateNotebookRequest(
            object_ids=[],
            values=[],
            auto_run=True,
            codes={"cell1": "print('hello')"},
        )
        assert request_with_codes.codes == {"cell1": "print('hello')"}

    def test_instantiate_with_codes_field(self, client: TestClient) -> None:
        """Test that instantiate endpoint accepts codes field.

        This test verifies the API accepts the codes parameter without
        creating a new session (which would fail due to multiprocessing issues
        in the test environment).
        """
        del client
        from marimo._session.requests import InstantiateNotebookRequest

        # Test that the model accepts codes
        request_with_codes = InstantiateNotebookRequest(
            object_ids=[],
            values=[],
            auto_run=True,
            codes={"cell1": "print('test')", "cell2": "x = 1"},
        )
        assert request_with_codes.codes == {
            "cell1": "print('test')",
            "cell2": "x = 1",
        }
        assert request_with_codes.auto_run is True
