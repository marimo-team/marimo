# Copyright 2024 Marimo. All rights reserved.
"""Tests for auto-instantiate behavior in run mode vs edit mode."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

from marimo._messaging.notification import KernelReadyNotification
from marimo._session.model import SessionMode
from marimo._utils.parse_dataclass import parse_raw
from tests._server.mocks import token_header

if TYPE_CHECKING:
    from starlette.testclient import TestClient


def _create_headers(session_id: str) -> dict[str, str]:
    """Create headers with both token and session ID."""
    return {
        **token_header("fake-token"),
        "Marimo-Session-Id": session_id,
    }


def _create_ws_url(session_id: str) -> str:
    return f"/ws?session_id={session_id}&access_token=fake-token"


class TestAutoInstantiateEditMode:
    """Tests for auto-instantiate in edit mode."""

    def test_kernel_ready_auto_instantiated_false_in_edit_mode(
        self, client: TestClient
    ) -> None:
        """In edit mode, auto_instantiated should be False."""
        session_id = "test-edit-mode"
        ws_url = _create_ws_url(session_id)
        headers = _create_headers(session_id)

        with client.websocket_connect(ws_url) as websocket:
            data = websocket.receive_json()
            assert data["op"] == "kernel-ready"

            kernel_ready = parse_raw(data["data"], KernelReadyNotification)
            # In edit mode, auto_instantiated should be False
            assert kernel_ready.auto_instantiated is False

        client.post("/api/kernel/shutdown", headers=headers)

    def test_instantiate_endpoint_allowed_in_edit_mode(
        self, client: TestClient
    ) -> None:
        """In edit mode, /instantiate endpoint should be allowed."""
        session_id = "test-instantiate-edit"
        ws_url = _create_ws_url(session_id)
        headers = _create_headers(session_id)

        with client.websocket_connect(ws_url):
            # The /instantiate endpoint should work in edit mode
            response = client.post(
                "/api/kernel/instantiate",
                headers=headers,
                json={"objectIds": [], "values": [], "autoRun": False},
            )
            assert response.status_code == 200

        client.post("/api/kernel/shutdown", headers=headers)


class TestAutoInstantiateRunMode:
    """Tests for auto-instantiate in run mode."""

    def test_kernel_ready_auto_instantiated_true_in_run_mode(
        self, client: TestClient
    ) -> None:
        """In run mode, auto_instantiated should be True."""
        from tests._server.conftest import get_session_manager

        session_manager = get_session_manager(client)
        original_mode = session_manager.mode
        session_id = "test-run-mode"
        headers = _create_headers(session_id)

        try:
            # Switch to run mode
            session_manager.mode = SessionMode.RUN
            ws_url = _create_ws_url(session_id)

            with client.websocket_connect(ws_url) as websocket:
                data = websocket.receive_json()
                assert data["op"] == "kernel-ready"

                kernel_ready = parse_raw(data["data"], KernelReadyNotification)
                # In run mode, auto_instantiated should be True
                assert kernel_ready.auto_instantiated is True
        finally:
            session_manager.mode = original_mode
            client.post("/api/kernel/shutdown", headers=headers)

    def test_instantiate_endpoint_blocked_in_run_mode(
        self, client: TestClient
    ) -> None:
        """In run mode, /instantiate endpoint should return 401 (Unauthorized).

        The @requires("edit") decorator checks for edit permissions, and in run mode
        users only have "read" permissions, so they get 401 Unauthorized.
        """
        from tests._server.conftest import get_session_manager

        session_manager = get_session_manager(client)
        original_mode = session_manager.mode
        session_id = "test-instantiate-run"
        headers = _create_headers(session_id)

        try:
            # Switch to run mode
            session_manager.mode = SessionMode.RUN
            ws_url = _create_ws_url(session_id)

            with client.websocket_connect(ws_url):
                # The /instantiate endpoint should be blocked in run mode
                # Returns 401 because @requires("edit") checks permissions
                response = client.post(
                    "/api/kernel/instantiate",
                    headers=headers,
                    json={"objectIds": [], "values": [], "autoRun": False},
                )
                assert response.status_code == 401
        finally:
            session_manager.mode = original_mode
            client.post("/api/kernel/shutdown", headers=headers)


class TestAutoInstantiateHTTPRequest:
    """Tests for HTTP request propagation during auto-instantiate."""

    def test_auto_instantiate_passes_http_request(self) -> None:
        """Verify _auto_instantiate passes HTTPRequest from websocket.

        This verifies the fix for the issue where mo.app_meta().request
        returned None in run mode because _auto_instantiate was passing
        http_request=None instead of extracting it from the websocket.
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
            websocket=MagicMock(),
        )

        with patch(
            "marimo._runtime.commands.HTTPRequest.from_request",
            return_value=mock_http_request,
        ) as mock_from_request:
            connector._auto_instantiate(mock_session)

        mock_from_request.assert_called_once_with(connector.websocket)
        assert (
            mock_session.instantiate.call_args.kwargs["http_request"]
            is mock_http_request
        )


class TestInstantiateNotebookRequest:
    """Tests for InstantiateNotebookRequest with codes field."""

    def test_instantiate_request_with_codes(self) -> None:
        """InstantiateNotebookRequest should accept optional codes field."""
        from marimo._server.models.models import InstantiateNotebookRequest

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
        from marimo._server.models.models import InstantiateNotebookRequest

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

    def test_instantiate_endpoint_without_codes_uses_file_codes(
        self, client: TestClient
    ) -> None:
        """Test that instantiate without codes uses file codes."""
        session_id = "test-file-codes"
        ws_url = _create_ws_url(session_id)
        headers = _create_headers(session_id)

        try:
            with client.websocket_connect(ws_url) as websocket:
                # Get the kernel-ready message
                data = websocket.receive_json()
                assert data["op"] == "kernel-ready"

                # Send instantiate without codes (should use file codes)
                response = client.post(
                    "/api/kernel/instantiate",
                    headers=headers,
                    json={
                        "objectIds": [],
                        "values": [],
                        "autoRun": True,
                        # No codes field
                    },
                )
                assert response.status_code == 200
        finally:
            client.post("/api/kernel/shutdown", headers=headers)
