# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import json
import sys
import time
from typing import TYPE_CHECKING, Any

import pytest

from marimo._types.ids import CellId_t, SessionId
from marimo._utils.lists import first
from tests._server.conftest import get_session_manager
from tests._server.mocks import token_header, with_read_session, with_session

if TYPE_CHECKING:
    from starlette.testclient import TestClient

SESSION_ID = SessionId("session-123")
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
                "auto_run": True,
            },
        )
        assert response.status_code == 200, response.text
        assert response.headers["content-type"] == "application/json"
        assert "success" in response.json()

    @staticmethod
    @with_session(SESSION_ID)
    def test_instantiate_autorun_false(client: TestClient) -> None:
        response = client.post(
            "/api/kernel/instantiate",
            headers=HEADERS,
            json={
                "object_ids": ["ui-element-1", "ui-element-2"],
                "values": ["value1", "value2"],
                "auto_run": False,
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
    def test_set_model_value(client: TestClient) -> None:
        response = client.post(
            "/api/kernel/set_model_value",
            headers=HEADERS,
            json={
                "model_id": "model-1",
                "message": {
                    "state": {"key": "value"},
                    "buffer_paths": [["a"], ["b"]],
                },
                "buffers": ["buffer1", "buffer2"],
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

    @staticmethod
    @with_session(SESSION_ID)
    def test_takeover_no_file_key(client: TestClient) -> None:
        response = client.post(
            "/api/kernel/takeover",
            headers=HEADERS,
        )
        assert response.status_code == 200, response.text
        assert response.headers["content-type"] == "application/json"
        assert response.json()["status"] == "ok"

    @staticmethod
    @with_session(SESSION_ID)
    def test_takeover_file_key(client: TestClient) -> None:
        response = client.post(
            "/api/kernel/takeover?file=test.py",
            headers=HEADERS,
        )
        assert response.status_code == 200, response.text
        assert response.headers["content-type"] == "application/json"
        assert response.json()["status"] == "ok"

    @staticmethod
    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="Skipping test on Windows due to websocket issues",
    )
    @with_session(SESSION_ID)
    def test_app_meta_request(client: TestClient) -> None:
        response = client.post(
            "/api/kernel/run",
            headers=HEADERS,
            json={
                "cell_ids": ["test-1"],
                "codes": [
                    "import marimo as mo\n"
                    "import json\n"
                    "request = dict(mo.app_meta().request)\n"
                    "request['user'] = bool(request['user'])\n"  # user is not serializable
                    "print(json.dumps(request))"
                ],
            },
        )
        assert response.status_code == 200, response.text
        assert response.headers["content-type"] == "application/json"
        assert "success" in response.json()

        # Sleep for 1 second (test)
        time.sleep(1.0)

        # Check keys
        app_meta_response = get_printed_object(client, "test-1")
        assert set(app_meta_response.keys()) == {
            "base_url",
            "cookies",
            "headers",
            "user",
            "meta",
            "path_params",
            "query_params",
            "url",
        }
        # Check no marimo in headers
        assert all(
            "marimo" not in header
            for header in app_meta_response["headers"].keys()
        )
        # Check user is False
        assert app_meta_response["user"] is True


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
                "auto_run": True,
            },
        )
        assert response.status_code == 200, response.text
        assert response.headers["content-type"] == "application/json"
        assert "success" in response.json()

    @staticmethod
    @with_read_session(SESSION_ID)
    def test_instantiate_autorun_false(client: TestClient) -> None:
        response = client.post(
            "/api/kernel/instantiate",
            headers=HEADERS,
            json={
                "object_ids": ["ui-element-1", "ui-element-2"],
                "values": ["value1", "value2"],
                "auto_run": False,
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
    def test_set_model_value(client: TestClient) -> None:
        response = client.post(
            "/api/kernel/set_model_value",
            headers=HEADERS,
            json={
                "model_id": "model-1",
                "message": {
                    "state": {"key": "value"},
                    "buffer_paths": [["a"], ["b"]],
                },
                "buffers": ["buffer1", "buffer2"],
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

    @staticmethod
    @with_read_session(SESSION_ID)
    def test_takeover_no_file_key(client: TestClient) -> None:
        response = client.post("/api/kernel/takeover", headers=HEADERS)
        assert response.status_code == 401, response.text

    @staticmethod
    @with_session(SESSION_ID)
    def with_read_session(client: TestClient) -> None:
        response = client.post(
            "/api/kernel/run",
            headers=HEADERS,
            json={
                "cell_ids": ["test-1"],
                "codes": [
                    "import marimo as mo\n"
                    "import json\n"
                    "request = dict(mo.app_meta().request)\n"
                    "request['user'] = bool(request['user'])\n"  # user is not serializable
                    "print(json.dumps(request))"
                ],
            },
        )
        assert response.status_code == 200, response.text
        assert response.headers["content-type"] == "application/json"
        assert "success" in response.json()

        # Sleep for .5 seconds
        time.sleep(0.5)

        # Check keys
        app_meta_response = get_printed_object(client, "test-1")
        assert set(app_meta_response.keys()) == {
            "base_url",
            "cookies",
            "headers",
            "user",
            "path_params",
            "query_params",
            "url",
        }
        # Check no marimo in headers
        assert all(
            "marimo" not in header
            for header in app_meta_response["headers"].keys()
        )
        # Check user is True
        assert app_meta_response["user"] is True


def get_printed_object(
    client: TestClient, cell_id: CellId_t
) -> dict[str, Any]:
    session = get_session_manager(client).get_session(SESSION_ID)
    assert session

    timeout = 4
    start = time.time()
    console = None
    while time.time() - start < timeout:
        if cell_id not in session.session_view.cell_operations:
            time.sleep(0.1)
            continue
        console = first(session.session_view.cell_operations[cell_id].console)
        if console:
            break
    assert console
    assert isinstance(console.data, str)
    return json.loads(console.data)
