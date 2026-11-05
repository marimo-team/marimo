# Copyright 2026 Marimo. All rights reserved.
"""Table selection and functions through a real host kernel."""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any

import pytest

from marimo._plugins import ui
from marimo._plugins.ui._impl.table import SearchTableArgs
from tests._server.host.drive import finished, request, until_ready, wait_for
from tests._server.host.live import AUTH, key, open_host
from tests._server.host.test_host_ui_elements import run_cells, snapshot

if TYPE_CHECKING:
    from pathlib import Path

SOURCE = """import marimo
app = marimo.App()

@app.cell
def _():
    import marimo as mo
    from marimo._runtime.context import get_context as _context
    from marimo._runtime.functions import Function as _Function, EmptyArgs as _EmptyArgs
    _changes = []
    table = mo.ui.table(["banana", "apple", "cherry"], on_change=_changes.append)
    def _inspect(_args):
        return {"value": table._value, "changes": _changes}
    _context().function_registry.register(table._id, _Function("inspect", _EmptyArgs, _inspect))
    table
    return (table,)
"""


async def test_table_queries_and_selection_preserve_shared_search_context(
    tmp_path: Path,
) -> None:
    baseline = ui.table(["banana", "apple", "cherry"])
    async with open_host(tmp_path, SOURCE) as (app, notebook_id, events):
        await run_cells(app, notebook_id, events)
        element = next(
            r["data"]["ui_element"]
            for r in events.records
            if r.get("event") == "ui_element"
        )
        assert element["config"]["component"] == "marimo-table"
        assert element["state"] == {"value": []}
        root = f"/notebooks/{notebook_id}/ui-elements/{element['id']}"

        async def send(name: str, args: dict[str, Any], request_id: str):
            response = await finished(
                app,
                "POST",
                f"{root}/send",
                headers=key(request_id),
                body=json.dumps(
                    {"message": {"function": name, "args": args}}
                ).encode(),
            )
            assert response.status == 200, response.body
            result = response.json()["result"]
            assert result["found"] is True
            assert result["status"]["code"] == "ok", result
            return result["return_value"]

        peer, task, disconnect = request(
            app,
            "GET",
            f"/notebooks/{notebook_id}/events",
            headers=AUTH,
            query="types=ui_element",
        )
        try:
            await wait_for(peer, until_ready)
            expected_changes = []
            # Each view has its own query; conversion uses the latest kernel search.
            for index, query in enumerate(("apple", "cherry")):
                args = {"query": query, "page_number": 0, "page_size": 1}
                baseline._search(SearchTableArgs(**args))
                result = await send("search", args, f"view-{index}-search")
                assert result["total_rows"] == 1
                expected = baseline._convert_value(["0"])
                expected_changes.append(expected)
                request_id = f"view-{index}-select"
                body = b'{"state":{"value":["0"]}}'
                response = await finished(
                    app,
                    "POST",
                    f"{root}/update",
                    headers=key(request_id),
                    body=body,
                )
                assert response.status == 202
                assert (
                    await finished(
                        app,
                        "POST",
                        f"{root}/update",
                        headers=key(request_id),
                        body=body,
                    )
                ).json() == response.json()
                for stream in (events, peer):
                    await wait_for(
                        stream,
                        lambda s, request_id=request_id: any(
                            r.get("event") == "ui_element.update"
                            and r["data"].get("request_id") == request_id
                            for r in s.records
                        ),
                    )
                    assert (
                        sum(
                            r.get("event") == "ui_element.update"
                            and r["data"].get("request_id") == request_id
                            for r in stream.records
                        )
                        == 1
                    )
                assert await send("inspect", {}, f"inspect-{index}") == {
                    "value": expected,
                    "changes": expected_changes,
                }

            for name, args in (
                ("get_row_ids", {}),
                ("get_data_url", {}),
                ("get_column_summaries", {}),
                ("get_export_metadata", {}),
                ("download_as", {"format": "csv"}),
                ("download_geojson", {"format": "geojson"}),
                ("calculate_top_k_rows", {"column": "value", "k": 2}),
                ("preview_column", {"column": "value"}),
                ("get_size_bytes", {}),
            ):
                await send(name, args, name)

            current = await snapshot(app, notebook_id, "types=ui_element")
            retained = next(
                r["data"]["ui_element"]
                for r in current
                if r.get("event") == "ui_element"
            )
            assert retained["state"] == {"value": ["0"]}
            for stream in (events, peer):
                assert not any(
                    r.get("data", {}).get("request_id", "").endswith("-search")
                    for r in stream.records
                )
            before = len(events.records)
            await run_cells(app, notebook_id, events, "rerun")
            assert [
                r["event"]
                for r in events.records[before:]
                if r.get("event", "").startswith("ui_element")
            ] == ["ui_element.removed", "ui_element"]
        finally:
            disconnect()
            await asyncio.wait_for(task, 5)


async def test_lazy_table_pages_through_host(tmp_path: Path) -> None:
    pytest.importorskip("polars")
    source = SOURCE.replace(
        'table = mo.ui.table(["banana", "apple", "cherry"], on_change=_changes.append)',
        'import polars as pl\n    table = mo.ui.table.lazy(pl.DataFrame({"value": list(range(100))}).lazy(), page_size=5)',
    )
    async with open_host(tmp_path, source) as (app, notebook_id, events):
        await run_cells(app, notebook_id, events)
        element = next(
            r["data"]["ui_element"]
            for r in events.records
            if r.get("event") == "ui_element"
        )
        assert element["config"]["args"]["lazy"] is True
        response = await finished(
            app,
            "POST",
            f"/notebooks/{notebook_id}/ui-elements/{element['id']}/send",
            headers=key("page"),
            body=b'{"message":{"function":"search","args":{"page_number":1,"page_size":5}}}',
        )
        assert response.status == 200, response.body
        result = response.json()["result"]
        assert result["status"]["code"] == "ok", result
        page = result["return_value"]
        assert page["total_rows"] == "too_many"
        assert page["has_next_page"] is True
        assert json.loads(page["data"]) == [
            {"value": value} for value in range(5, 10)
        ]


@pytest.mark.parametrize("selection", ["multi", "multi-cell"])
async def test_dataframe_selection_through_host(
    tmp_path: Path, selection: str
) -> None:
    pytest.importorskip("polars")
    source = SOURCE.replace(
        'table = mo.ui.table(["banana", "apple", "cherry"], on_change=_changes.append)',
        f'import polars as pl\n    table = mo.ui.table(pl.DataFrame({{"value": [10, 20, 30]}}), selection="{selection}")',
    ).replace(
        '"value": table._value',
        '"value": table._value.to_dicts() if hasattr(table._value, "to_dicts") else [cell.value for cell in table._value]',
    )
    async with open_host(tmp_path, source) as (app, notebook_id, events):
        await run_cells(app, notebook_id, events)
        element = next(
            r["data"]["ui_element"]
            for r in events.records
            if r.get("event") == "ui_element"
        )
        root = f"/notebooks/{notebook_id}/ui-elements/{element['id']}"
        wire = (
            ["1"]
            if selection == "multi"
            else [{"rowId": "1", "columnName": "value"}]
        )
        response = await finished(
            app,
            "POST",
            f"{root}/update",
            headers=key("select"),
            body=json.dumps({"state": {"value": wire}}).encode(),
        )
        assert response.status == 202, response.body
        await wait_for(
            events,
            lambda s: any(
                r.get("event") == "ui_element.update"
                and r["data"].get("request_id") == "select"
                for r in s.records
            ),
        )
        inspected = await finished(
            app,
            "POST",
            f"{root}/send",
            headers=key("inspect"),
            body=b'{"message":{"function":"inspect","args":{}}}',
        )
        assert inspected.status == 200, inspected.body
        result = inspected.json()["result"]
        assert result["status"]["code"] == "ok", result
        assert result["return_value"]["value"] == (
            [{"value": 20}] if selection == "multi" else [20]
        )
