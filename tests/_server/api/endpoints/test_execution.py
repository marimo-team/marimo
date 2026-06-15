# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import json
import sys
import time
from typing import TYPE_CHECKING

import pytest

from marimo._types.ids import CellId_t, SessionId
from marimo._utils.lists import first
from tests._server.api.endpoints.ws_helpers import (
    HEADERS as WS_HEADERS,
    assert_kernel_ready_response,
    create_response,
    receive_until,
)
from tests._server.mocks import (
    get_session_manager,
    token_header,
    with_read_session,
    with_session,
)

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
                "objectIds": ["ui-element-1", "ui-element-2"],
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
                "objectIds": ["ui-element-1", "ui-element-2"],
                "values": ["value1", "value2"],
                "autoRun": True,
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
                "objectIds": ["ui-element-1", "ui-element-2"],
                "values": ["value1", "value2"],
                "autoRun": False,
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
                "functionCallId": "call-123",
                "namespace": "namespace1",
                "functionName": "function1",
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
                "modelId": "model-1",
                "message": {
                    "method": "update",
                    "state": {"key": "value"},
                    "bufferPaths": [["a"], ["b"]],
                },
                "buffers": ["YnVmZmVyMQ==", "YnVmZmVyMg=="],
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
    @with_session(SESSION_ID)
    def test_kernel_status(client: TestClient) -> None:
        response = client.get("/api/kernel/status", headers=HEADERS)
        assert response.status_code == 200, response.text
        assert response.headers["content-type"] == "application/json"
        assert response.json()["state"] in ("running", "idle", "stopped")

    @staticmethod
    @with_session(SESSION_ID)
    def test_kernel_status_running(client: TestClient) -> None:
        from marimo._messaging.notification import CellNotification

        session = get_session_manager(client).get_session(SESSION_ID)
        assert session is not None
        # Seed a synthetic running cell the real kernel never emits, so a
        # concurrent idle broadcast for the notebook's own cells can't race
        # this assertion.
        session.session_view.cell_notifications[CellId_t("status-test")] = (
            CellNotification(cell_id=CellId_t("status-test"), status="running")
        )
        response = client.get("/api/kernel/status", headers=HEADERS)
        assert response.status_code == 200, response.text
        assert response.json()["state"] == "running"

    @staticmethod
    @with_session(SESSION_ID)
    def test_kernel_status_idle(client: TestClient) -> None:
        session = get_session_manager(client).get_session(SESSION_ID)
        assert session is not None
        session.session_view.cell_notifications.clear()
        response = client.get("/api/kernel/status", headers=HEADERS)
        assert response.status_code == 200, response.text
        assert response.json()["state"] == "idle"

    @staticmethod
    def test_restart_session(client: TestClient) -> None:
        with client.websocket_connect(
            f"/ws?session_id={SESSION_ID}&access_token=fake-token"
        ) as websocket:
            data = websocket.receive_text()
            assert data
        response = client.post("/api/kernel/restart_session", headers=HEADERS)
        assert response.status_code == 200, response.text
        assert response.headers["content-type"] == "application/json"
        assert "success" in response.json()

    @staticmethod
    @with_session(SESSION_ID)
    def test_run_cell(client: TestClient) -> None:
        response = client.post(
            "/api/kernel/run",
            headers=HEADERS,
            json={
                "cellIds": ["cell-1", "cell-2"],
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
    def test_execute_injects_screenshot_meta(client: TestClient) -> None:
        """`/api/kernel/execute` injects a trusted server URL + auth token
        into `HTTPRequest.meta` so `ctx.screenshot()` can authenticate
        Playwright against this server.  Regression guard: deleting either
        injection line in the endpoint should fail this test.
        """
        from unittest.mock import patch

        from marimo._runtime.commands import ExecuteScratchpadCommand
        from marimo._server import scratchpad as scratchpad_mod

        session = get_session_manager(client).get_session(SESSION_ID)
        assert session is not None

        captured: list[object] = []

        def capture(req: object, from_consumer_id: object) -> None:  # noqa: ARG001
            captured.append(req)

        async def empty_stream(self: object):  # noqa: ARG001
            if False:
                yield ""  # makes this an async generator that yields nothing

        with (
            patch.object(session, "put_control_request", side_effect=capture),
            patch.object(
                scratchpad_mod.ScratchCellListener,
                "stream",
                empty_stream,
            ),
        ):
            response = client.post(
                "/api/kernel/execute",
                headers=HEADERS,
                json={"code": "x = 1"},
            )

        assert response.status_code == 200, response.text

        scratchpad_cmds = [
            c for c in captured if isinstance(c, ExecuteScratchpadCommand)
        ]
        assert len(scratchpad_cmds) == 1, (
            f"expected one ExecuteScratchpadCommand, got {captured!r}"
        )
        meta = scratchpad_cmds[0].request.meta
        assert meta["screenshot_auth_token"] == "fake-token"
        # Mock server uses host="localhost", port=1234, base_url=""
        assert meta["screenshot_server_url"] == "http://localhost:1234"

    @staticmethod
    @with_session(SESSION_ID)
    def test_execute_attaches_cell_outputs_snapshot(
        client: TestClient,
    ) -> None:
        """`/api/kernel/execute` must populate `cell_outputs` from the
        session view so code_mode can expose `cell.output` and
        `cell.console_outputs`.  Regression guard: removing the
        construction line in the endpoint should fail this test.
        """
        from unittest.mock import patch

        from marimo._messaging.cell_output import CellChannel, CellOutput
        from marimo._messaging.notification import CellNotification
        from marimo._runtime.commands import ExecuteScratchpadCommand
        from marimo._server import scratchpad as scratchpad_mod

        session = get_session_manager(client).get_session(SESSION_ID)
        assert session is not None

        # Seed the session view with an output for an existing cell so
        # we can assert it survives the round-trip to the command.
        cell_id = first(session.document.cell_ids)
        sample = CellOutput(
            channel=CellChannel.OUTPUT,
            mimetype="text/plain",
            data="42",
        )
        sample_console = CellOutput.stdout("hello\n")
        session.session_view.cell_notifications[cell_id] = CellNotification(
            cell_id=cell_id,
            output=sample,
            console=[sample_console],
        )

        captured: list[object] = []

        def capture(req: object, from_consumer_id: object) -> None:  # noqa: ARG001
            captured.append(req)

        async def empty_stream(self: object):  # noqa: ARG001
            if False:
                yield ""

        with (
            patch.object(session, "put_control_request", side_effect=capture),
            patch.object(
                scratchpad_mod.ScratchCellListener,
                "stream",
                empty_stream,
            ),
        ):
            response = client.post(
                "/api/kernel/execute",
                headers=HEADERS,
                json={"code": "x = 1"},
            )

        assert response.status_code == 200, response.text

        scratchpad_cmds = [
            c for c in captured if isinstance(c, ExecuteScratchpadCommand)
        ]
        assert len(scratchpad_cmds) == 1
        cell_outputs = scratchpad_cmds[0].cell_outputs
        assert cell_outputs is not None
        assert cell_outputs.output[cell_id] is sample
        assert cell_outputs.console_outputs[cell_id] == [sample_console]

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
    def test_takeover_missing_session_id_header(client: TestClient) -> None:
        response = client.post(
            "/api/kernel/takeover",
            headers=token_header("fake-token"),
        )
        assert response.status_code == 400, response.text

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
    @pytest.mark.flaky(reruns=5)
    @with_session(SESSION_ID)
    def test_app_meta_request(client: TestClient) -> None:
        response = client.post(
            "/api/kernel/run",
            headers=HEADERS,
            json={
                "cellIds": ["test-1"],
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
            "marimo" not in header for header in app_meta_response["headers"]
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
                "objectIds": ["ui-element-1", "ui-element-2"],
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
                "objectIds": ["ui-element-1", "ui-element-2"],
                "values": ["value1", "value2"],
                "autoRun": True,
            },
        )
        assert response.status_code == 401, response.text

    @staticmethod
    @with_read_session(SESSION_ID)
    def test_instantiate_autorun_false(client: TestClient) -> None:
        response = client.post(
            "/api/kernel/instantiate",
            headers=HEADERS,
            json={
                "objectIds": ["ui-element-1", "ui-element-2"],
                "values": ["value1", "value2"],
                "autoRun": False,
            },
        )
        assert response.status_code == 401, response.text

    @staticmethod
    @with_read_session(SESSION_ID)
    def test_function_call(client: TestClient) -> None:
        response = client.post(
            "/api/kernel/function_call",
            headers=HEADERS,
            json={
                "functionCallId": "call-123",
                "namespace": "namespace1",
                "functionName": "function1",
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
                "modelId": "model-1",
                "message": {
                    "method": "update",
                    "state": {"key": "value"},
                    "bufferPaths": [["a"], ["b"]],
                },
                "buffers": ["YnVmZmVyMQ==", "YnVmZmVyMg=="],
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
    def test_kernel_status(client: TestClient) -> None:
        response = client.get("/api/kernel/status", headers=HEADERS)
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
                "cellIds": ["cell-1", "cell-2"],
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
    @pytest.mark.flaky(reruns=5)
    @with_session(SESSION_ID)
    def test_app_meta_request(client: TestClient) -> None:
        response = client.post(
            "/api/kernel/run",
            headers=HEADERS,
            json={
                "cellIds": ["test-1"],
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
            "meta",
            "path_params",
            "query_params",
            "url",
        }
        # Check no marimo in headers
        assert all(
            "marimo" not in header for header in app_meta_response["headers"]
        )
        # Check user is True
        assert app_meta_response["user"] is True


def get_printed_object(
    client: TestClient, cell_id: CellId_t
) -> dict[str, object]:
    session = get_session_manager(client).get_session(SESSION_ID)
    assert session

    timeout = 4
    start = time.time()
    console = None
    while time.time() - start < timeout:
        if cell_id not in session.session_view.cell_notifications:
            time.sleep(0.1)
            continue
        console = first(
            session.session_view.cell_notifications[cell_id].console
        )
        if console:
            break
    assert console
    if console.mimetype in (
        "application/vnd.marimo+error",
        "application/vnd.marimo+traceback",
    ):
        pytest.fail(f"Console is an error: {console.data}")
    assert isinstance(console.data, str)
    return json.loads(console.data)


def test_takeover_transfers_edit_without_disconnect(
    client: TestClient,
) -> None:
    with client.websocket_connect(
        "/ws?session_id=ed1", headers=WS_HEADERS
    ) as editor:
        assert_kernel_ready_response(editor.receive_json())
        with client.websocket_connect(
            "/ws?session_id=vw1", headers=WS_HEADERS
        ) as viewer:
            assert_kernel_ready_response(
                viewer.receive_json(),
                create_response(
                    {
                        "kiosk": True,
                        "resumed": True,
                        "consumer_capabilities": {
                            "edit": False,
                            "interact": False,
                        },
                    }
                ),
            )

            resp = client.post(
                "/api/kernel/takeover",
                headers={**WS_HEADERS, "Marimo-Session-Id": "vw1"},
            )
            assert resp.status_code == 200, resp.text

            ed = receive_until("consumer-capabilities", editor)
            vw = receive_until("consumer-capabilities", viewer)
            assert ed["data"]["consumer_capabilities"] == {
                "edit": False,
                "interact": False,
            }
            assert vw["data"]["consumer_capabilities"] == {
                "edit": True,
                "interact": True,
            }
