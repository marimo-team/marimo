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
