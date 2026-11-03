# Copyright 2026 Marimo. All rights reserved.
"""Slider behavior through public host operations and event streams."""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any

from tests._server.host.drive import finished, request, until_ready, wait_for
from tests._server.host.live import AUTH, key, open_host

if TYPE_CHECKING:
    from pathlib import Path

    from starlette.applications import Starlette

    from tests._server.host.drive import Response

SOURCE = """import marimo
app = marimo.App()

@app.cell
def _():
    import marimo as mo
    slider = mo.ui.slider(0, 10, value=3, label="x")
    slider
    return (slider,)
"""


async def run_cells(
    app: Starlette, notebook_id: str, events: Response, request_id: str = "run"
) -> None:
    cells = [
        r["data"]["cell"] for r in events.records if r.get("event") == "cell"
    ]
    response = await finished(
        app,
        "POST",
        f"/notebooks/{notebook_id}/runtime/runs",
        headers=key(request_id),
        body=json.dumps(
            {"cells": [{"id": cell["id"]} for cell in cells]}
        ).encode(),
    )
    assert response.status == 202, response.body
    await wait_for(
        events,
        lambda stream: any(
            r.get("event") == "run"
            and r["data"]["run"]["id"] == response.json()["id"]
            and r["data"]["run"]["status"] == "completed"
            for r in stream.records
        ),
    )


async def snapshot(
    app: Starlette, notebook_id: str, query: str = ""
) -> list[dict[str, Any]]:
    events, task, disconnect = request(
        app,
        "GET",
        f"/notebooks/{notebook_id}/events",
        headers=AUTH,
        query=query,
    )
    try:
        await wait_for(events, until_ready)
        return events.records.copy()
    finally:
        disconnect()
        await asyncio.wait_for(task, 5)


async def test_slider_creation_is_retained_without_a_view(
    tmp_path: Path,
) -> None:
    async with open_host(tmp_path, SOURCE) as (app, notebook_id, events):
        await run_cells(app, notebook_id, events)
        records = [r for r in events.records if r.get("event") == "ui_element"]
        assert len(records) == 1
        record = records[0]["data"]["ui_element"]
        assert record["state"] == {"value": 3}
        assert record["kind"] == "element"
        assert record["config"]["component"] == "marimo-slider"
        assert record["config"]["label"] == "x"
        assert record["id"] == f"{record['cell_id']}-0"
        completed = next(
            r
            for r in events.records
            if r.get("event") == "execution"
            and r["data"]["execution"]["status"] == "completed"
        )
        assert events.records.index(records[0]) < events.records.index(
            completed
        )
        assert (
            "marimo-slider"
            in completed["data"]["execution"]["outcome"]["display"]["data"]
        )
        current = await snapshot(app, notebook_id)
        retained = [r for r in current if r.get("event") == "ui_element"]
        assert retained == [
            {"event": "ui_element", "data": {"ui_element": record}}
        ]
        names = [r.get("event") for r in current]
        assert (
            names.index("attachment")
            < names.index("ui_element")
            < names.index("execution")
        )
        filtered = await snapshot(app, notebook_id, "types=ui_element")
        assert [
            r for r in filtered if r.get("event") == "ui_element"
        ] == retained
        excluded = await snapshot(app, notebook_id, "types=cell")
        assert "ui_element" not in [r.get("event") for r in excluded]
        replay = await snapshot(
            app, notebook_id, f"types=ui_element&cursor={records[0]['id']}"
        )
        assert "ui_element" not in [r.get("event") for r in replay]
        reset = await snapshot(
            app, notebook_id, "types=ui_element&cursor=expired"
        )
        assert [r for r in reset if r.get("event") == "ui_element"] == retained
        assert reset[0]["event"] == "reset"


async def test_slider_record_lifetime_follows_its_creating_cell(
    tmp_path: Path,
) -> None:
    async with open_host(tmp_path, SOURCE) as (app, notebook_id, events):
        await run_cells(app, notebook_id, events)
        first = next(
            r["data"]["ui_element"]
            for r in events.records
            if r.get("event") == "ui_element"
        )
        before = len(events.records)
        await run_cells(app, notebook_id, events, "rerun")
        changes = [
            r
            for r in events.records[before:]
            if r.get("event", "").startswith("ui_element")
        ]
        assert [r["event"] for r in changes] == [
            "ui_element.removed",
            "ui_element",
        ]
        assert changes[0]["data"]["id"] == first["id"]
        assert changes[1]["data"]["ui_element"] == first
        stopped = await finished(
            app,
            "DELETE",
            f"/notebooks/{notebook_id}/runtime",
            headers=key("stop"),
        )
        assert stopped.status == 202
        await wait_for(
            events, lambda stream: "runtime.removed" in stream.names()
        )
        assert events.names().index("runtime.removed") > max(
            i
            for i, r in enumerate(events.records)
            if r.get("event") == "ui_element.removed"
        )
        assert "ui_element" not in [
            r.get("event") for r in await snapshot(app, notebook_id)
        ]


async def test_deleting_owner_removes_slider_displayed_elsewhere(
    tmp_path: Path,
) -> None:
    source = SOURCE + "\n@app.cell\ndef _(slider):\n    slider\n    return\n"
    async with open_host(tmp_path, source) as (app, notebook_id, events):
        await run_cells(app, notebook_id, events)
        element = next(
            r["data"]["ui_element"]
            for r in events.records
            if r.get("event") == "ui_element"
        )
        response = await finished(
            app,
            "POST",
            f"/notebooks/{notebook_id}/edits",
            headers=key("delete-owner"),
            body=json.dumps(
                {
                    "changes": [
                        {
                            "kind": "delete_cell",
                            "id": element["cell_id"],
                            "base_etag": "*",
                        }
                    ]
                }
            ).encode(),
        )
        assert response.status == 200, response.body
        removed = [
            r["data"]["id"]
            for r in events.records
            if r.get("event") == "ui_element.removed"
        ]
        assert removed == [element["id"]]
        assert "ui_element" not in [
            r.get("event") for r in await snapshot(app, notebook_id)
        ]


async def test_host_updates_reach_every_attachment_once(
    tmp_path: Path,
) -> None:
    async with open_host(tmp_path, SOURCE) as (app, notebook_id, events):
        await run_cells(app, notebook_id, events)
        element = next(
            r["data"]["ui_element"]
            for r in events.records
            if r.get("event") == "ui_element"
        )
        peer, task, disconnect = request(
            app,
            "GET",
            f"/notebooks/{notebook_id}/events",
            headers=AUTH,
            query="types=ui_element",
        )
        try:
            await wait_for(peer, until_ready)
            route = (
                f"/notebooks/{notebook_id}/ui-elements/{element['id']}/update"
            )
            for request_id in ("write", "unchanged"):
                response = await finished(
                    app,
                    "POST",
                    route,
                    headers=key(request_id),
                    body=b'{"state":{"value":4}}',
                )
                assert response.status == 202, response.body
                assert response.json() == {
                    "id": element["id"],
                    "state": {"value": 4},
                    "request_id": request_id,
                }
                retried = await finished(
                    app,
                    "POST",
                    route,
                    headers=key(request_id),
                    body=b'{"state":{"value":4}}',
                )
                assert retried.json() == response.json()
                for stream in (events, peer):
                    await wait_for(
                        stream,
                        lambda s, request_id=request_id: any(
                            r.get("event") == "ui_element.update"
                            and r["data"].get("request_id") == request_id
                            for r in s.records
                        ),
                    )
                    updates = [
                        r
                        for r in stream.records
                        if r.get("event") == "ui_element.update"
                        and r["data"].get("request_id") == request_id
                    ]
                    assert len(updates) == 1
                    assert updates[0]["data"]["state"] == {"value": 4}
            current = await snapshot(app, notebook_id)
            assert next(
                r["data"]["ui_element"]["state"]
                for r in current
                if r.get("event") == "ui_element"
            ) == {"value": 4}
        finally:
            disconnect()
            await asyncio.wait_for(task, 5)


async def test_queued_acceptance_does_not_change_confirmed_state(
    tmp_path: Path,
) -> None:
    async with open_host(tmp_path, SOURCE) as (app, notebook_id, events):
        await run_cells(app, notebook_id, events)
        element = next(
            r["data"]["ui_element"]
            for r in events.records
            if r.get("event") == "ui_element"
        )
        busy = await finished(
            app,
            "POST",
            f"/notebooks/{notebook_id}/runtime/runs",
            headers=key("busy"),
            body=b'{"code":"import time; time.sleep(1)"}',
        )
        await wait_for(
            events,
            lambda stream: any(
                r.get("event") == "run"
                and r["data"]["run"]["id"] == busy.json()["id"]
                and r["data"]["run"]["status"] == "running"
                for r in stream.records
            ),
        )
        route = f"/notebooks/{notebook_id}/ui-elements/{element['id']}/update"
        for request_id, state in (
            ("four", {"value": 4}),
            ("five", {"value": 5}),
            ("empty", {}),
        ):
            response = await finished(
                app,
                "POST",
                route,
                headers=key(request_id),
                body=json.dumps({"state": state}).encode(),
            )
            assert response.status == 202, response.body
        retained = await snapshot(app, notebook_id, "types=ui_element")
        assert next(
            r["data"]["ui_element"]["state"]
            for r in retained
            if r.get("event") == "ui_element"
        ) == {"value": 3}
        await wait_for(
            events,
            lambda stream: any(
                r.get("event") == "ui_element.update"
                and r["data"].get("request_id") == "empty"
                for r in stream.records
            ),
        )
        updates = [
            r["data"]
            for r in events.records
            if r.get("event") == "ui_element.update"
        ]
        assert [(r["request_id"], r["state"]) for r in updates] == [
            ("four", {"value": 4}),
            ("five", {"value": 5}),
            ("empty", {}),
        ]
        retained = await snapshot(app, notebook_id, "types=ui_element")
        assert next(
            r["data"]["ui_element"]["state"]
            for r in retained
            if r.get("event") == "ui_element"
        ) == {"value": 5}


async def test_invalid_updates_leave_no_acknowledgements(
    tmp_path: Path,
) -> None:
    async with open_host(tmp_path, SOURCE) as (app, notebook_id, events):
        await run_cells(app, notebook_id, events)
        element = next(
            r["data"]["ui_element"]
            for r in events.records
            if r.get("event") == "ui_element"
        )
        route = f"/notebooks/{notebook_id}/ui-elements/{element['id']}/update"
        for index, body in enumerate(
            (
                {},
                {"state": []},
                {"state": {"unknown": 4}},
                {"state": {}, "extra": True},
            )
        ):
            response = await finished(
                app,
                "POST",
                route,
                headers=key(f"invalid-{index}"),
                body=json.dumps(body).encode(),
            )
            assert response.status == 400, response.body
        missing = await finished(
            app,
            "POST",
            f"/notebooks/{notebook_id}/ui-elements/missing/update",
            headers=key("missing"),
            body=b'{"state":{"value":4}}',
        )
        assert missing.status == 404
        forbidden = await finished(
            app,
            "POST",
            route,
            headers={"Idempotency-Key": "unauthorized"},
            body=b'{"state":{"value":4}}',
        )
        assert forbidden.status == 401
        stopped = await finished(
            app,
            "DELETE",
            f"/notebooks/{notebook_id}/runtime",
            headers=key("stop"),
        )
        assert stopped.status == 202
        await wait_for(
            events, lambda stream: "runtime.removed" in stream.names()
        )
        no_runtime = await finished(
            app,
            "POST",
            route,
            headers=key("no-runtime"),
            body=b'{"state":{"value":4}}',
        )
        assert no_runtime.status == 409
        assert no_runtime.json()["type"].endswith("/no-runtime")
        assert "ui_element.update" not in events.names()


async def test_dependent_failure_does_not_undo_applied_value(
    tmp_path: Path,
) -> None:
    source = (
        SOURCE
        + """
@app.cell
def _(slider):
    assert slider.value != 4, "dependent failed"
    return
"""
    )
    async with open_host(tmp_path, source) as (app, notebook_id, events):
        await run_cells(app, notebook_id, events)
        element = next(
            r["data"]["ui_element"]
            for r in events.records
            if r.get("event") == "ui_element"
        )
        response = await finished(
            app,
            "POST",
            f"/notebooks/{notebook_id}/ui-elements/{element['id']}/update",
            headers=key("fail-dependent"),
            body=b'{"state":{"value":4}}',
        )
        assert response.status == 202
        await wait_for(
            events,
            lambda stream: any(
                r.get("event") == "execution"
                and r["data"]["execution"]["status"] == "completed"
                and r["data"]["execution"].get("outcome", {}).get("kind")
                == "error"
                for r in stream.records
            ),
        )
        retained = await snapshot(app, notebook_id, "types=ui_element")
        assert next(
            r["data"]["ui_element"]["state"]
            for r in retained
            if r.get("event") == "ui_element"
        ) == {"value": 4}
        assert (
            len(
                [
                    r
                    for r in events.records
                    if r.get("event") == "ui_element.update"
                ]
            )
            == 1
        )


async def test_composite_slider_clones_keep_the_legacy_path(
    tmp_path: Path,
) -> None:
    source = SOURCE.replace(
        "    slider\n    return (slider,)",
        "    form = slider.form()\n    form\n    return (slider, form)",
    )
    async with open_host(tmp_path, source) as (app, notebook_id, events):
        await run_cells(app, notebook_id, events)
        records = [
            r["data"]["ui_element"]
            for r in events.records
            if r.get("event") == "ui_element"
        ]
        assert len(records) == 1
        assert records[0]["id"] == f"{records[0]['cell_id']}-0"
        clone = await finished(
            app,
            "POST",
            f"/notebooks/{notebook_id}/ui-elements/{records[0]['cell_id']}-1/update",
            headers=key("clone"),
            body=b'{"state":{"value":4}}',
        )
        assert clone.status == 404
