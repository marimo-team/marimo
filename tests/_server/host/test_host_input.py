# Copyright 2026 Marimo. All rights reserved.
"""Input prompts and replies through the host API and a real kernel."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from tests._server.host.drive import finished, wait_for
from tests._server.host.live import key, open_host

if TYPE_CHECKING:
    from pathlib import Path


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
            f"/notebooks/{notebook_id}/runtime/runs",
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
                        and r["data"]["run"]["status"] == "completed"
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
                    r["data"]["execution"]["outcome"]
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
                and record["data"]["run"]["status"] == "completed"
                for record in response.records
            ),
        )
        [run] = [
            record["data"]["run"]
            for record in events.records
            if record.get("event") == "run"
            and record["data"]["run"]["status"] == "completed"
        ]
        assert run["outcome"] == "succeeded"
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
            runs,
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
                and record["data"]["run"]["status"] == "completed"
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
