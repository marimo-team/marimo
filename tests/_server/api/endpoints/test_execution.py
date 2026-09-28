# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest

from marimo._code_mode.screenshot_meta import (
    SCREENSHOT_AUTH_TOKEN_KEY,
    SCREENSHOT_FILE_KEY,
    SCREENSHOT_SERVER_URL_KEY,
)
from marimo._messaging.notification import ConsumerCapabilities
from marimo._runtime.commands import ExecuteCellsCommand
from marimo._server.api.utils import enforce_consumer_capability
from marimo._types.ids import CellId_t, SessionId
from marimo._utils.http import HTTPException
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
    from collections.abc import AsyncGenerator
    from contextlib import AbstractContextManager

    from httpx import Response
    from starlette.testclient import TestClient

    from marimo._session import Session

SESSION_ID = SessionId("session-123")
HEADERS = {
    "Marimo-Session-Id": SESSION_ID,
    **token_header("fake-token"),
}
STABLE_SESSION_HEADER = "Marimo-Stable-Session-Id"
PARTICIPANT_ID_HEADER = "Marimo-Participant-Id"
PAIR_PREVIEW_ENV = "MARIMO_PAIR_NEXT"


def _pair_preview_enabled() -> AbstractContextManager[Any]:
    return patch.dict(os.environ, {PAIR_PREVIEW_ENV: "1"})


def _pair_preview_disabled() -> AbstractContextManager[Any]:
    environ = {k: v for k, v in os.environ.items() if k != PAIR_PREVIEW_ENV}
    return patch.dict(os.environ, environ, clear=True)


def _participant_headers(
    session: Session, participant_id: str, *, harness: str = "claude"
) -> dict[str, str]:
    return {
        STABLE_SESSION_HEADER: session.stable_id,
        PARTICIPANT_ID_HEADER: participant_id,
        "Marimo-Participant-Harness": harness,
        **token_header("fake-token"),
    }


def _execute_without_kernel(
    client: TestClient, session: Session, headers: dict[str, str]
) -> Response:
    """POST `/api/kernel/execute` with kernel dispatch and streaming replaced.

    The request still passes authentication, session resolution, and the
    participant guard.
    """
    from marimo._server import scratchpad as scratchpad_mod

    async def empty_stream(
        self: object,  # noqa: ARG001
    ) -> AsyncGenerator[str, None]:
        if False:
            yield ""

    with (
        patch.object(session, "put_control_request"),
        patch.object(
            scratchpad_mod.ScratchCellListener, "stream", empty_stream
        ),
    ):
        return client.post(
            "/api/kernel/execute", headers=headers, json={"code": "x = 1"}
        )


def _count_execute_interrupts(
    client: TestClient, *, watcher_fires: bool, stream_cancelled: bool
) -> int:
    """POST `/api/kernel/execute` with a simulated client disconnect and
    return how many times the session interrupted the kernel.

    Args:
        client (TestClient): Client with a live session `SESSION_ID`.
        watcher_fires (bool): The disconnect watcher sees the disconnect.
        stream_cancelled (bool): The response stream is cancelled.
    """
    from unittest.mock import patch

    from marimo._server import scratchpad as scratchpad_mod

    session = get_session_manager(client).get_session(SESSION_ID)
    assert session is not None

    async def wait_for_disconnect(request: object) -> None:  # noqa: ARG001
        if not watcher_fires:
            await asyncio.Event().wait()

    async def stream(self: object):  # noqa: ARG001
        # Yield to the event loop so the watcher task runs first.
        await asyncio.sleep(0.05)
        if stream_cancelled:
            raise asyncio.CancelledError()
        if False:
            yield ""

    with (
        patch(
            "marimo._server.api.endpoints.execution.wait_for_http_disconnect",
            wait_for_disconnect,
        ),
        patch.object(scratchpad_mod.ScratchCellListener, "stream", stream),
        patch.object(session, "put_control_request"),
        patch.object(session, "try_interrupt") as try_interrupt,
    ):
        response = client.post(
            "/api/kernel/execute",
            headers=HEADERS,
            json={"code": "x = 1"},
        )

    assert response.status_code == 200, response.text
    return try_interrupt.call_count


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
    def test_execute_with_stable_session_id(client: TestClient) -> None:
        from unittest.mock import patch

        from marimo._runtime.commands import ExecuteScratchpadCommand
        from marimo._server import scratchpad as scratchpad_mod

        session = get_session_manager(client).get_session(SESSION_ID)
        assert session is not None

        captured: list[object] = []

        def capture(req: object, from_consumer_id: object) -> None:  # noqa: ARG001
            captured.append(req)

        async def empty_stream(
            self: object,  # noqa: ARG001
        ) -> AsyncGenerator[str, None]:
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
                headers={
                    STABLE_SESSION_HEADER: session.stable_id,
                    **token_header("fake-token"),
                },
                json={"code": "x = 1"},
            )

        assert response.status_code == 200, response.text
        scratchpad_commands = [
            command
            for command in captured
            if isinstance(command, ExecuteScratchpadCommand)
        ]
        assert len(scratchpad_commands) == 1
        assert scratchpad_commands[0].code == "x = 1"

    @staticmethod
    @with_session(SESSION_ID)
    def test_execute_rejects_conflicting_session_ids(
        client: TestClient,
    ) -> None:
        session = get_session_manager(client).get_session(SESSION_ID)
        assert session is not None

        response = client.post(
            "/api/kernel/execute",
            headers={
                **HEADERS,
                STABLE_SESSION_HEADER: session.stable_id,
            },
            json={"code": "x = 1"},
        )

        assert response.status_code == 400, response.text
        assert response.json() == {
            "detail": (
                "Marimo-Stable-Session-Id cannot be combined with "
                "Marimo-Session-Id."
            )
        }

    @staticmethod
    @with_session(SESSION_ID)
    def test_execute_rejects_unknown_stable_session_id(
        client: TestClient,
    ) -> None:
        response = client.post(
            "/api/kernel/execute",
            headers={
                STABLE_SESSION_HEADER: "sess-unknown",
                **token_header("fake-token"),
            },
            json={"code": "x = 1"},
        )

        assert response.status_code == 404, response.text
        assert response.json() == {
            "detail": "Invalid stable session id: sess-unknown"
        }

    @staticmethod
    @with_session(SESSION_ID)
    def test_execute_with_participant_records_contact(
        client: TestClient,
    ) -> None:
        session = get_session_manager(client).get_session(SESSION_ID)
        assert session is not None

        with _pair_preview_enabled():
            first = _execute_without_kernel(
                client, session, _participant_headers(session, "p1")
            )
            first_presence = session.session_view.participant_presence
            second = _execute_without_kernel(
                client, session, _participant_headers(session, "p1")
            )

        assert first.status_code == 200, first.text
        assert second.status_code == 200, second.text
        assert first_presence is not None
        presence = session.session_view.participant_presence
        assert presence is not None
        assert presence.participant_id == "p1"
        assert presence.harness == "claude"
        assert presence.kind == "agent"
        assert presence.attached is True
        assert presence.last_contact_at >= first_presence.last_contact_at

    @staticmethod
    @with_session(SESSION_ID)
    def test_execute_rejects_second_live_participant(
        client: TestClient,
    ) -> None:
        session = get_session_manager(client).get_session(SESSION_ID)
        assert session is not None

        with _pair_preview_enabled():
            first = _execute_without_kernel(
                client, session, _participant_headers(session, "p1")
            )
            second = _execute_without_kernel(
                client,
                session,
                _participant_headers(session, "p2", harness="codex"),
            )

        assert first.status_code == 200, first.text
        assert second.status_code == 409, second.text
        assert second.json() == {
            "detail": (
                "Another participant (claude) is attached to this session."
            )
        }
        presence = session.session_view.participant_presence
        assert presence is not None
        assert presence.participant_id == "p1"
        assert presence.attached is True

    @staticmethod
    @with_session(SESSION_ID)
    def test_execute_participant_requires_stable_session_header(
        client: TestClient,
    ) -> None:
        with _pair_preview_enabled():
            response = client.post(
                "/api/kernel/execute",
                headers={**HEADERS, PARTICIPANT_ID_HEADER: "p1"},
                json={"code": "x = 1"},
            )

        assert response.status_code == 400, response.text
        assert response.json() == {
            "detail": (
                "Marimo-Participant-Id requires Marimo-Stable-Session-Id."
            )
        }

    @staticmethod
    @with_session(SESSION_ID)
    def test_execute_rejects_unknown_participant_kind(
        client: TestClient,
    ) -> None:
        session = get_session_manager(client).get_session(SESSION_ID)
        assert session is not None

        with _pair_preview_enabled():
            response = _execute_without_kernel(
                client,
                session,
                {
                    **_participant_headers(session, "p1"),
                    "Marimo-Participant-Kind": "robot",
                },
            )

        assert response.status_code == 400, response.text
        assert response.json() == {
            "detail": "Marimo-Participant-Kind must be one of human, agent."
        }
        assert session.session_view.participant_presence is None

    @staticmethod
    @with_session(SESSION_ID)
    def test_execute_ignores_participant_header_without_preview(
        client: TestClient,
    ) -> None:
        session = get_session_manager(client).get_session(SESSION_ID)
        assert session is not None

        with _pair_preview_disabled():
            response = _execute_without_kernel(
                client, session, _participant_headers(session, "p1")
            )

        assert response.status_code == 200, response.text
        assert session.session_view.participant_presence is None

    @staticmethod
    @with_session(SESSION_ID)
    def test_execute_injects_screenshot_meta(client: TestClient) -> None:
        """Inject the trusted server URL, auth token, and notebook key
        so screenshots authenticate and attach to the active notebook.
        """
        from unittest.mock import PropertyMock, patch

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

        for path in [None, "notebooks/my notebook.py"]:
            captured.clear()
            with (
                patch.object(
                    type(session.app_file_manager),
                    "path",
                    new_callable=PropertyMock,
                    return_value=path,
                ),
                patch.object(
                    session, "put_control_request", side_effect=capture
                ),
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
            http_req = scratchpad_cmds[0].request
            assert http_req is not None
            # Mock server uses host="localhost", port=1234, base_url=""
            assert http_req.meta[SCREENSHOT_SERVER_URL_KEY] == (
                "http://localhost:1234"
            )
            assert http_req.meta[SCREENSHOT_AUTH_TOKEN_KEY] == "fake-token"
            assert http_req.meta[SCREENSHOT_FILE_KEY] == (
                path or session.initialization_id
            )

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
    def test_execute_interrupts_kernel_on_watched_disconnect(
        client: TestClient,
    ) -> None:
        """On ASGI spec >= 2.4 servers only the disconnect watcher sees
        the disconnect. It must interrupt the kernel."""
        assert (
            _count_execute_interrupts(
                client, watcher_fires=True, stream_cancelled=False
            )
            == 1
        )

    @staticmethod
    @with_session(SESSION_ID)
    def test_execute_interrupts_kernel_on_cancelled_response(
        client: TestClient,
    ) -> None:
        """On ASGI spec < 2.4 servers the response is cancelled and the
        watcher never fires. The cancellation must interrupt the kernel."""
        assert (
            _count_execute_interrupts(
                client, watcher_fires=False, stream_cancelled=True
            )
            == 1
        )

    @staticmethod
    @with_session(SESSION_ID)
    def test_execute_interrupts_kernel_once_per_disconnect(
        client: TestClient,
    ) -> None:
        """On ASGI spec 2.3 servers both the disconnect watcher and the
        response cancellation observe one client disconnect. The kernel
        must receive one interrupt, not two."""
        assert (
            _count_execute_interrupts(
                client, watcher_fires=True, stream_cancelled=True
            )
            == 1
        )

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
                    (
                        "import marimo as mo\n"
                        "import json\n"
                        "request = dict(mo.app_meta().request)\n"
                        # user is not serializable
                        "request['user'] = bool(request['user'])\n"
                        "print(json.dumps(request))"
                    )
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
                    (
                        "import marimo as mo\n"
                        "import json\n"
                        "request = dict(mo.app_meta().request)\n"
                        # user is not serializable
                        "request['user'] = bool(request['user'])\n"
                        "print(json.dumps(request))"
                    )
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
                            "interact": True,
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
                "interact": True,
            }
            assert vw["data"]["consumer_capabilities"] == {
                "edit": True,
                "interact": True,
            }


def _app_state_for_consumer(caps: ConsumerCapabilities) -> object:
    app_state = MagicMock()
    app_state.require_current_session_id.return_value = "consumer-1"
    session = app_state.require_current_session.return_value
    session.room.get_consumer.return_value = object()
    session.room.get_capabilities.return_value = caps
    return app_state


def test_enforce_consumer_capability_blocks_viewer() -> None:
    # A default viewer is an interactor (edit=False); an edit-tier command is
    # still refused.
    app_state = _app_state_for_consumer(ConsumerCapabilities.INTERACTOR)
    command = ExecuteCellsCommand(cell_ids=[], codes=[])
    with pytest.raises(HTTPException) as exc_info:
        enforce_consumer_capability(app_state, command)  # type: ignore[arg-type]
    assert exc_info.value.status_code == 403


def test_enforce_consumer_capability_allows_editor() -> None:
    app_state = _app_state_for_consumer(ConsumerCapabilities.EDITOR)
    command = ExecuteCellsCommand(cell_ids=[], codes=[])
    enforce_consumer_capability(app_state, command)  # type: ignore[arg-type]
