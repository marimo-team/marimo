# Copyright 2026 Marimo. All rights reserved.
"""Registered function calls through the public host route and a real kernel."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from tests._server.host.drive import finished
from tests._server.host.live import key, open_host
from tests._server.host.test_host_ui_elements import run_cells, snapshot

if TYPE_CHECKING:
    from pathlib import Path


SOURCE = """import marimo
app = marimo.App()

@app.cell
def _():
    import marimo as mo
    from marimo._runtime.context import get_context as _get_context
    from marimo._runtime.functions import Function as _Function, EmptyArgs as _EmptyArgs
    slider = mo.ui.slider(0, 10, value=3)
    _calls = []
    def _read(_args):
        _calls.append(1)
        return {"calls": len(_calls), "value": slider._value}
    def _fail(_args):
        raise ValueError("function failed")
    for _name, _fn in [("read", _read), ("fail", _fail)]:
        _get_context().function_registry.register(
            slider._id, _Function(_name, _EmptyArgs, _fn)
        )
    slider
    return (slider,)
"""


async def test_send_returns_private_results_and_reuses_receipts(
    tmp_path: Path,
) -> None:
    async with open_host(tmp_path, SOURCE) as (app, notebook_id, events):
        await run_cells(app, notebook_id, events)
        element = next(
            r["data"]["ui_element"]
            for r in events.records
            if r.get("event") == "ui_element"
        )
        path = f"/notebooks/{notebook_id}/ui-elements/{element['id']}/send"

        async def send(name: str, request_id: str):
            return await finished(
                app,
                "POST",
                path,
                headers=key(request_id),
                body=json.dumps(
                    {"message": {"function": name, "args": {}}}
                ).encode(),
            )

        one = await send("read", "read-once")
        assert one.status == 200, one.body
        assert one.json() == {
            "request_id": "read-once",
            "result": {
                "found": True,
                "status": {"code": "ok", "title": None, "message": None},
                "return_value": {"calls": 1, "value": 3},
            },
        }
        again = await send("read", "read-once")
        assert again.json() == one.json()
        second = await send("read", "read-twice")
        assert second.json()["result"]["return_value"]["calls"] == 2
        missing = await send("missing", "missing")
        assert missing.status == 200
        assert missing.json()["result"]["found"] is False
        failed = await send("fail", "failed")
        assert failed.status == 200
        assert failed.json()["result"]["found"] is True
        assert failed.json()["result"]["status"]["code"] == "error"
        assert (
            "function failed" in failed.json()["result"]["status"]["message"]
        )
        assert (await send("fail", "failed")).json() == failed.json()

        replay = await snapshot(app, notebook_id, "cursor=0")
        for records in (events.records, replay):
            assert not any(
                r.get("data", {}).get("marimo", {}).get("op")
                in ("ui-element-result", "function-call-result")
                for r in records
            )
            assert "read-once" not in json.dumps(records)

        unauthenticated = await finished(
            app,
            "POST",
            path,
            headers={"Idempotency-Key": "no-auth"},
            body=b'{"message":{"function":"read","args":{}}}',
        )
        assert unauthenticated.status == 401
        malformed = await finished(
            app,
            "POST",
            path,
            headers=key("malformed"),
            body=b'{"message":{"function":"read","args":[]}}',
        )
        assert malformed.status == 400
        buffers = await finished(
            app,
            "POST",
            path,
            headers=key("buffers"),
            body=b'{"message":{"function":"read","args":{}},"buffers":["AA=="]}',
        )
        assert buffers.status == 501
        absent = await finished(
            app,
            "POST",
            f"/notebooks/{notebook_id}/ui-elements/absent/send",
            headers=key("absent"),
            body=b'{"message":{"function":"read","args":{}}}',
        )
        assert absent.status == 404
