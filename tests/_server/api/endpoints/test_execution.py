# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

from tests._server.conftest import get_session_manager
from tests._server.mocks import token_header, with_read_session, with_session

if TYPE_CHECKING:
    from starlette.testclient import TestClient

SESSION_ID = "session-123"
HEADERS = {
    "Marimo-Session-Id": SESSION_ID,
    **token_header("fake-token"),
}


class TestExecutionRoutes_EditMode:
    @staticmethod
    @with_session(SESSION_ID)
    def test_set_ui_element_value(client: TestClient) -> None:
        response = client.post(
            "/api/kernel/set_ui_element_value",
            headers=HEADERS,
            json={
                "object_ids": ["ui-element-1", "ui-element-2"],
                "values": ["value1", "value2"],
            },
        )
        assert response.status_code == 200, response.text
        assert response.headers["content-type"] == "application/json"
        assert "success" in response.json()

    @staticmethod
    @with_session(SESSION_ID)
    def test_instantiate(client: TestClient) -> None:
        response = client.post(
            "/api/kernel/instantiate",
            headers=HEADERS,
            json={
                "object_ids": ["ui-element-1", "ui-element-2"],
                "values": ["value1", "value2"],
            },
        )
        assert response.status_code == 200, response.text
        assert response.headers["content-type"] == "application/json"
        assert "success" in response.json()

    @staticmethod
    @with_session(SESSION_ID)
    def test_function_call(client: TestClient) -> None:
        response = client.post(
            "/api/kernel/function_call",
            headers=HEADERS,
            json={
                "function_call_id": "call-123",
                "namespace": "namespace1",
                "function_name": "function1",
                "args": {"arg1": "value1"},
            },
        )
        assert response.status_code == 200, response.text
        assert response.headers["content-type"] == "application/json"
        assert "success" in response.json()

    @staticmethod
    @with_session(SESSION_ID)
    def test_interrupt(client: TestClient) -> None:
        response = client.post("/api/kernel/interrupt", headers=HEADERS)
        assert response.status_code == 200, response.text
        assert response.headers["content-type"] == "application/json"
        assert "success" in response.json()

    @staticmethod
    def test_restart_session(client: TestClient) -> None:
        with client.websocket_connect(
            f"/ws?session_id={SESSION_ID}"
        ) as websocket:
            data = websocket.receive_text()
            assert data
        response = client.post("/api/kernel/restart_session", headers=HEADERS)
        assert response.status_code == 200, response.text
        assert response.headers["content-type"] == "application/json"
        assert "success" in response.json()
        auth_token = get_session_manager(client).auth_token
        client.post(
            "/api/kernel/shutdown",
            headers=token_header(auth_token),
        )

    @staticmethod
    @with_session(SESSION_ID)
    def test_run_cell(client: TestClient) -> None:
        response = client.post(
            "/api/kernel/run",
            headers=HEADERS,
            json={
                "cell_ids": ["cell-1", "cell-2"],
                "codes": ["print('Hello, cell-1')", "print('Hello, cell-2')"],
            },
        )
        assert response.status_code == 200, response.text
        assert response.headers["content-type"] == "application/json"
        assert "success" in response.json()

    @staticmethod
    @with_session(SESSION_ID)
    def test_run_scratchpad(client: TestClient) -> None:
        response = client.post(
            "/api/kernel/scratchpad/run",
            headers=HEADERS,
            json={"code": "print('Hello, scratchpad')"},
        )
        assert response.status_code == 200, response.text
        assert response.headers["content-type"] == "application/json"
        assert "success" in response.json()


class TestExecutionRoutes_RunMode:
    @staticmethod
    @with_read_session(SESSION_ID)
    def test_set_ui_element_value(client: TestClient) -> None:
        response = client.post(
            "/api/kernel/set_ui_element_value",
            headers=HEADERS,
            json={
                "object_ids": ["ui-element-1", "ui-element-2"],
                "values": ["value1", "value2"],
            },
        )
        assert response.status_code == 200, response.text
        assert response.headers["content-type"] == "application/json"
        assert "success" in response.json()

    @staticmethod
    @with_read_session(SESSION_ID)
    def test_instantiate(client: TestClient) -> None:
        response = client.post(
            "/api/kernel/instantiate",
            headers=HEADERS,
            json={
                "object_ids": ["ui-element-1", "ui-element-2"],
                "values": ["value1", "value2"],
            },
        )
        assert response.status_code == 200, response.text
        assert response.headers["content-type"] == "application/json"
        assert "success" in response.json()

    @staticmethod
    @with_read_session(SESSION_ID)
    def test_function_call(client: TestClient) -> None:
        response = client.post(
            "/api/kernel/function_call",
            headers=HEADERS,
            json={
                "function_call_id": "call-123",
                "namespace": "namespace1",
                "function_name": "function1",
                "args": {"arg1": "value1"},
            },
        )
        assert response.status_code == 200, response.text
        assert response.headers["content-type"] == "application/json"
        assert "success" in response.json()

    @staticmethod
    @with_read_session(SESSION_ID)
    def test_interrupt(client: TestClient) -> None:
        response = client.post("/api/kernel/interrupt", headers=HEADERS)
        assert response.status_code == 401, response.text

    @staticmethod
    @with_read_session(SESSION_ID)
    def test_restart_session(client: TestClient) -> None:
        response = client.post("/api/kernel/restart_session", headers=HEADERS)
        assert response.status_code == 401, response.text

    @staticmethod
    @with_read_session(SESSION_ID)
    def test_run_cell(client: TestClient) -> None:
        response = client.post(
            "/api/kernel/run",
            headers=HEADERS,
            json={
                "cell_ids": ["cell-1", "cell-2"],
                "codes": ["print('Hello, cell-1')", "print('Hello, cell-2')"],
            },
        )
        assert response.status_code == 401, response.text

    @staticmethod
    @with_read_session(SESSION_ID)
    def test_run_scratchpad(client: TestClient) -> None:
        response = client.post(
            "/api/kernel/scratchpad/run",
            headers=HEADERS,
            json={"code": "print('Hello, scratchpad')"},
        )
        assert response.status_code == 401, response.text
