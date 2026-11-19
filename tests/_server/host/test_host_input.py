# Copyright 2026 Marimo. All rights reserved.
"""Input prompts and replies through the host API and a real kernel."""

from __future__ import annotations

import json
from contextlib import ExitStack
from textwrap import dedent
from typing import TYPE_CHECKING

import pytest

from marimo._messaging.notification import ConsumerCapabilities
from marimo._server.host import HOST_API_PATH
from marimo._session.state.serialize import serialize_session_view
from marimo._types.ids import CellId_t, ConsumerId, SessionId
from tests._server.api.endpoints.ws_helpers import headers, receive_until
from tests._server.host.drive import finished, socket_snapshot, wait_for
from tests._server.host.live import key, open_host
from tests._server.mocks import get_session_manager

if TYPE_CHECKING:
    from pathlib import Path

    from httpx import Response
    from starlette.testclient import TestClient, WebSocketTestSession


@pytest.mark.parametrize("kiosk", [False, True])
def test_editor_input_replies_require_interact(
    client: TestClient, kiosk: bool
) -> None:
    with (
        client,
        client.websocket_connect(
            "/ws?session_id=editor", headers=headers("editor")
        ) as editor,
    ):
        snapshot = socket_snapshot(editor)
        notebook_id = next(
            event["data"]["notebook"]["id"]
            for event in snapshot
            if event["event"] == "notebook"
        )
        receive_until("kernel-ready", editor)
        url = "/ws?session_id=other" + ("&kiosk=true" if kiosk else "")
        with client.websocket_connect(url, headers=headers("other")) as other:
            ready = receive_until("kernel-ready", other)
            assert ready["data"]["consumer_capabilities"] == {
                "edit": False,
                "interact": True,
            }
            base = f"{HOST_API_PATH}/notebooks/{notebook_id}/runtime"
            accepted = client.post(
                f"{base}/execute",
                headers={**headers("editor"), "Idempotency-Key": "run"},
                json={"code": "assert input('Prompt: ') == 'answer'"},
            )
            assert accepted.status_code == 202, accepted.text
            while True:
                event = editor.receive_json()
                if event["event"] == "run":
                    run = event["data"]["run"]
                    if run["id"] == accepted.json()["id"]:
                        assert run["state"]["status"] != "completed", run
                if event["event"] == "input":
                    pending = event["data"]["input"]
                    break
            assert pending["status"] == "pending"
            path = f"{base}/inputs/{pending['id']}/reply"

            session = get_session_manager(client).get_session(
                SessionId("other")
            )
            assert session is not None
            consumer = session.room.get_consumer(ConsumerId("other"))
            assert consumer is not None
            session.room.add_consumer(
                consumer, main=False, capabilities=ConsumerCapabilities.VIEWER
            )
            for connection in ("other", "never-connected"):
                refused = client.post(
                    path,
                    headers={
                        **headers(connection),
                        "Idempotency-Key": f"refused-{connection}",
                    },
                    json={"value": "wrong answer"},
                )
                assert refused.status_code == 403, refused.text
                assert refused.json()["type"] == "urn:marimo:problem:forbidden"
            session.room.add_consumer(
                consumer,
                main=False,
                capabilities=ConsumerCapabilities.INTERACTOR,
            )
            reply = client.post(
                path,
                headers={**headers("other"), "Idempotency-Key": "answer"},
                json={"value": "answer"},
            )
            assert reply.status_code == 200, reply.text
            assert reply.json() == {**pending, "status": "answered"}
            while True:
                event = editor.receive_json()
                if event["event"] == "run":
                    run = event["data"]["run"]
                    if (
                        run["id"] == accepted.json()["id"]
                        and run["state"]["status"] == "completed"
                    ):
                        break
            assert run["state"]["outcome"] == "succeeded"


@pytest.mark.parametrize("scratch", [False, True])
async def test_input_replies_and_retries(
    tmp_path: Path, scratch: bool
) -> None:
    code = "import getpass\n_secret = getpass.getpass('Password: ')\n_blank = input('Empty: ')\nassert _secret == 'secret' and _blank == ''"
    source = (
        "import marimo\napp = marimo.App()\n@app.cell\ndef _():\n"
        + "\n".join("    " + line for line in code.splitlines())
        + "\n    return\n"
    )
    async with open_host(tmp_path, source) as (app, notebook_id, events):
        context = app.state.host_context
        notebook = await context.bridge.host.notebook(notebook_id)
        session_id = next(iter(app.state.session_manager.sessions))
        payload = (
            {"code": code}
            if scratch
            else {"cells": [{"id": next(iter(notebook.document)).id}]}
        )
        accepted = await finished(
            app,
            "POST",
            f"/notebooks/{notebook_id}/runtime/{'execute' if scratch else 'runs'}",
            headers={**key("run"), "Marimo-Session-Id": session_id},
            body=json.dumps(payload).encode(),
        )
        assert accepted.status == 202, accepted.body
        for index, value in enumerate(("secret", "")):
            await wait_for(
                events,
                lambda response, index=index: (
                    len(
                        [
                            record
                            for record in response.records
                            if record.get("event") == "input"
                            and record["data"]["input"]["status"] == "pending"
                        ]
                    )
                    > index
                    or any(
                        r.get("event") == "run"
                        and r["data"]["run"]["state"]["status"] == "completed"
                        for r in response.records
                    )
                ),
            )
            assert (
                len(
                    [
                        r
                        for r in events.records
                        if r.get("event") == "input"
                        and r["data"]["input"]["status"] == "pending"
                    ]
                )
                > index
            ), json.dumps(
                [
                    r["data"]["execution"]["state"]["outcome"]
                    for r in events.records
                    if r.get("event") == "execution"
                ]
            )
            pending = [
                record["data"]["input"]
                for record in events.records
                if record.get("event") == "input"
                and record["data"]["input"]["status"] == "pending"
            ][index]
            assert pending["password"] == (index == 0)
            path = f"/notebooks/{notebook_id}/runtime/inputs/{pending['id']}/reply"
            body = json.dumps({"value": value}).encode()
            reply = await finished(
                app, "POST", path, headers=key(f"answer-{index}"), body=body
            )
            assert reply.status == 200, reply.body
            assert reply.json() == {**pending, "status": "answered"}
            retried = await finished(
                app, "POST", path, headers=key(f"answer-{index}"), body=body
            )
            assert (retried.status, retried.json()) == (200, reply.json())
            duplicate = await finished(
                app, "POST", path, headers=key(f"duplicate-{index}"), body=body
            )
            assert duplicate.status == 409, duplicate.body
        await wait_for(
            events,
            lambda response: any(
                record.get("event") == "run"
                and record["data"]["run"]["state"]["status"] == "completed"
                for record in response.records
            ),
        )
        [run] = [
            record["data"]["run"]
            for record in events.records
            if record.get("event") == "run"
            and record["data"]["run"]["state"]["status"] == "completed"
        ]
        assert run["state"]["outcome"] == "succeeded"
        inputs = [
            record
            for record in events.records
            if record.get("event") == "input"
        ]
        assert "secret" not in json.dumps(inputs)
        assert [record["data"]["request_id"] for record in inputs] == [
            "run",
            "answer-0",
            "run",
            "answer-1",
        ]


async def test_interrupt_closes_prompt_and_rejects_late_reply(
    tmp_path: Path,
) -> None:
    async with open_host(tmp_path, "import marimo\napp = marimo.App()\n") as (
        app,
        notebook_id,
        events,
    ):
        session_id = next(iter(app.state.session_manager.sessions))
        runs = f"/notebooks/{notebook_id}/runtime/runs"
        accepted = await finished(
            app,
            "POST",
            f"/notebooks/{notebook_id}/runtime/execute",
            headers={**key("run"), "Marimo-Session-Id": session_id},
            body=b'{"code":"input()"}',
        )
        assert accepted.status == 202
        await wait_for(events, lambda response: "input" in response.names())
        pending = next(
            record["data"]["input"]
            for record in events.records
            if record.get("event") == "input"
        )
        interrupted = await finished(
            app,
            "DELETE",
            f"{runs}/{accepted.json()['id']}",
            headers=key("interrupt"),
        )
        assert interrupted.status == 202
        late = await finished(
            app,
            "POST",
            f"/notebooks/{notebook_id}/runtime/inputs/{pending['id']}/reply",
            headers=key("late"),
            body=b'{"value":"late"}',
        )
        assert late.status == 409
        await wait_for(
            events,
            lambda response: any(
                record.get("event") == "run"
                and record["data"]["run"]["state"]["status"] == "completed"
                for record in response.records
            ),
        )
        [cancelled] = [
            record["data"]
            for record in events.records
            if record.get("event") == "input"
            and record["data"]["input"]["status"] == "cancelled"
        ]
        assert cancelled["request_id"] == "interrupt"


def test_clear_console_hides_only_settled_input_on_reconnect(
    client: TestClient,
) -> None:
    with client:
        with client.websocket_connect(
            "/ws?session_id=editor", headers=headers("editor")
        ) as socket:
            notebook_id = next(
                frame["data"]["notebook"]["id"]
                for frame in socket_snapshot(socket)
                if frame["event"] == "notebook"
            )
            receive_until("kernel-ready", socket)
            base = f"{HOST_API_PATH}/notebooks/{notebook_id}/runtime"
            run = client.post(
                f"{base}/execute",
                headers={**headers("editor"), "Idempotency-Key": "run"},
                json={
                    "code": (
                        "import marimo as mo\n"
                        "input('first?')\n"
                        "mo.output.clear_console()\n"
                        "mo.output.clear_console()\n"
                        "input('second?')"
                    )
                },
            )
            assert run.status_code == 202, run.text
            while (event := socket.receive_json())["event"] != "input":
                pass
            first = event["data"]["input"]
            response = client.post(
                f"{base}/inputs/{first['id']}/reply",
                headers={**headers("editor"), "Idempotency-Key": "reply"},
                json={"value": "one"},
            )
            assert response.status_code == 200, response.text
            clears = []
            while True:
                event = socket.receive_json()
                if event["event"] == "marimo":
                    notification = event["data"]["marimo"]
                    if notification["op"] == "console-inputs-cleared":
                        clears.append(notification)
                if (
                    event["event"] == "input"
                    and event["data"]["input"]["prompt"] == "second?"
                ):
                    second = event["data"]["input"]
                    break
            assert len(clears) == 1
            assert clears[0]["input_ids"] == [first["id"]]
            assert clears[0]["execution_id"] == first["execution_id"]

        with client.websocket_connect(
            "/ws?session_id=resumed", headers=headers("resumed")
        ) as socket:
            snapshot = socket_snapshot(socket)
            inputs = {
                event["data"]["input"]["id"]: event["data"]["input"]["status"]
                for event in snapshot
                if event["event"] == "input"
            }
            assert inputs == {first["id"]: "answered", second["id"]: "pending"}
            assert (
                receive_until("console-inputs-cleared", socket)["data"]
                == clears[0]
            )
            response = client.post(
                f"{base}/inputs/{second['id']}/reply",
                headers={**headers("resumed"), "Idempotency-Key": "second"},
                json={"value": "two"},
            )
            assert response.status_code == 200, response.text


@pytest.mark.parametrize("finish", ["continue", "quit", "interrupt"])
def test_failed_cell_debugger_prompt_survives_reconnect(
    client: TestClient, finish: str
) -> None:
    get_session_manager(client).redirect_console_to_browser = True
    with client, ExitStack() as sockets:

        def connect(name: str) -> WebSocketTestSession:
            return sockets.enter_context(
                client.websocket_connect(
                    f"/ws?session_id={name}", headers=headers(name)
                )
            )

        editor = connect("editor")
        notebook = next(
            e["data"]["notebook"]
            for e in socket_snapshot(editor)
            if e["event"] == "notebook"
        )
        base = f"{HOST_API_PATH}/notebooks/{notebook['id']}"
        receive_until("kernel-ready", editor)
        edit = client.post(
            f"{base}/edits",
            headers={**headers("editor"), "Idempotency-Key": "edit"},
            json={
                "changes": [
                    {
                        "kind": "put_cell",
                        "base_etag": None,
                        "cell": {
                            "id": "probe",
                            "code": dedent("""
                                import marimo as mo
                                import os
                                import threading

                                def debug_output(native_line, thread_line):
                                    os.write(1, native_line.encode())
                                    for cls in (threading.Thread, mo.Thread):
                                        thread = cls(target=lambda: print(thread_line))
                                        thread.start()
                                        thread.join()

                                raise ValueError("debug me")
                            """),
                        },
                    }
                ]
            },
        )
        assert edit.status_code == 200, edit.text
        run = client.post(
            f"{base}/runtime/runs",
            headers={**headers("editor"), "Idempotency-Key": "run"},
            json={"cells": [{"id": "probe"}]},
        )
        assert run.status_code == 202, run.text
        while True:
            event = editor.receive_json()
            if event["event"] == "marimo":
                assert event["data"]["marimo"]["op"] not in {
                    "execution",
                    "cell-op",
                }
            if event["event"] == "execution":
                retained = event["data"]["execution"]
                if retained["state"]["status"] == "completed":
                    break
        assert retained["state"]["outcome"]["kind"] == "error"
        start = client.post(
            "/api/kernel/pdb/pm",
            headers=headers("editor"),
            json={"cellId": "probe"},
        )
        assert start.status_code == 200, start.text

        transcript = []

        def next_prompt(
            socket: WebSocketTestSession, *, expected_output: str | None = None
        ) -> str:
            prompt = None
            while True:
                event = socket.receive_json()
                if event["event"] != "marimo":
                    continue
                msg = event["data"]["marimo"]
                assert msg["op"] != "cell-op"
                if msg["op"] == "pdb-output":
                    assert msg["cell_id"] == "probe"
                    transcript.extend(
                        entry["data"] for entry in msg["entries"]
                    )
                if msg["op"] == "pdb-input" and isinstance(
                    msg["input_id"], str
                ):
                    assert msg["cell_id"] == "probe"
                    prompt = msg["input_id"]
                if prompt is not None and (
                    expected_output is None
                    or expected_output in "".join(transcript)
                ):
                    return prompt

        first = next_prompt(editor)
        initial_output = "".join(transcript)
        sockets.close()
        transcript.clear()
        editor = connect("resumed")
        assert next_prompt(editor) == first
        assert "".join(transcript) == initial_output

        def reply(prompt: str, value: str, name: str = "resumed") -> Response:
            return client.post(
                "/api/kernel/pdb/reply",
                headers=headers(name),
                json={"cellId": "probe", "inputId": prompt, "value": value},
            )

        viewer = connect("viewer")
        receive_until("kernel-ready", viewer)
        assert reply(first, "quit", "viewer").status_code == 403

        def takeover(name: str) -> None:
            response = client.post(
                "/api/kernel/takeover", headers=headers(name)
            )
            assert response.status_code == 200, response.text

        takeover("viewer")
        assert not receive_until("consumer-capabilities", editor)["data"][
            "consumer_capabilities"
        ]["edit"]
        assert receive_until("consumer-capabilities", viewer)["data"][
            "consumer_capabilities"
        ]["edit"]
        transcript.clear()
        assert next_prompt(viewer) == first
        assert "".join(transcript) == initial_output
        assert reply(first, "quit", "resumed").status_code == 403
        transcript.clear()
        native_line = "native debugger output"
        thread_line = "thread debugger output"
        command = f"p debug_output({native_line!r}, {thread_line!r})"
        assert reply(first, command, "viewer").status_code == 200
        second = next_prompt(viewer, expected_output=native_line)
        assert "".join(transcript).count(native_line) == 1
        assert "".join(transcript).count(thread_line) == 2
        assert first != second
        expected_output = initial_output + "".join(transcript)
        session = get_session_manager(client).get_session(SessionId("viewer"))
        assert session is not None
        export = serialize_session_view(
            session.session_view,
            [CellId_t("probe")],
            include_callback_output=True,
            drop_virtual_file_outputs=False,
        )
        console = json.dumps(export["cells"][0]["console"])
        assert native_line not in console
        assert thread_line not in console
        takeover("resumed")
        while True:
            event = editor.receive_json()
            assert native_line not in json.dumps(event)
            assert thread_line not in json.dumps(event)
            if event["event"] == "marimo":
                msg = event["data"]["marimo"]
                assert msg["op"] not in {"pdb-input", "pdb-output"}
                if (
                    msg["op"] == "consumer-capabilities"
                    and msg["consumer_capabilities"]["edit"]
                ):
                    break
        transcript.clear()
        assert next_prompt(editor) == second
        assert "".join(transcript) == expected_output
        sockets.close()
        transcript.clear()
        editor = connect("resumed")
        assert next_prompt(editor) == second
        assert "".join(transcript) == expected_output
        assert reply(first, "quit").status_code == 409
        if finish == "interrupt":
            interrupt = client.post(
                f"{base}/runtime/interrupt",
                headers={**headers("resumed"), "Idempotency-Key": "interrupt"},
            )
            assert interrupt.status_code == 202, interrupt.text
        else:
            assert reply(second, finish).status_code == 200
        assert receive_until("pdb-input", editor)["data"]["input_id"] is None
        assert reply(second, "late").status_code == 409
        resumed = client.post(
            f"{base}/runtime/execute",
            headers={
                **headers("resumed"),
                "Idempotency-Key": "after-debugging",
            },
            json={"code": "4"},
        )
        assert resumed.status_code == 202
        while True:
            event = editor.receive_json()
            if event["event"] == "run":
                completed_run = event["data"]["run"]
                if (
                    completed_run["id"] == resumed.json()["id"]
                    and completed_run["state"]["status"] == "completed"
                ):
                    assert completed_run["state"]["outcome"] == "succeeded"
                    break
        sockets.close()
        snapshot = socket_snapshot(connect("after"))
        assert [
            e["data"]["execution"]
            for e in snapshot
            if e["event"] == "execution"
            and e["data"]["execution"]["cell_id"] == "probe"
        ] == [retained]
        assert not any(e["event"] == "input" for e in snapshot)
