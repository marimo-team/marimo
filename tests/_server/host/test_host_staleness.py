# Copyright 2026 Marimo. All rights reserved.
"""Clients derive whether results are current from a real host's stream."""

from __future__ import annotations

import contextlib
import itertools
import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pytest

from tests._server.host.drive import finished, wait_for
from tests._server.host.live import key, open_host
from tests._server.host.staleness import snapshot

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path

    from starlette.applications import Starlette

    from marimo._config.config import OnCellChangeType
    from tests._server.host.drive import Response
    from tests._server.host.staleness import Outdated, Snapshot


def notebook(*cells: str) -> str:
    """A notebook source whose cells run `cells` in order."""
    body = "".join(
        "@app.cell\ndef _():\n"
        + "".join(f"    {line}\n" for line in code.splitlines())
        for code in cells
    )
    return f"import marimo\napp = marimo.App()\n{body}"


@dataclass
class Client:
    """A host client that refers to cells by name."""

    app: Starlette
    notebook_id: str
    events: Response
    cells: dict[str, str]
    _keys: itertools.count[int] = field(default_factory=itertools.count)

    async def run(self, *cells: str, code: str | None = None) -> None:
        """Run the named cells, or code in the scratchpad."""
        body: dict[str, object] = (
            {"code": code}
            if code is not None
            else {"cells": [{"id": self.cells[name]} for name in cells]}
        )
        accepted = await finished(
            self.app,
            "POST",
            f"/notebooks/{self.notebook_id}/runtime/runs",
            headers=key(f"run-{next(self._keys)}"),
            body=json.dumps(body).encode(),
        )
        assert accepted.status == 202, accepted.body
        run_id = accepted.json()["id"]
        await wait_for(
            self.events,
            lambda response: any(
                r.get("data", {}).get("run", {}).get("id") == run_id
                and r["data"]["run"]["status"] == "completed"
                for r in response.records
            ),
        )

    async def edit(self, cell: str, code: str) -> None:
        edited = await finished(
            self.app,
            "POST",
            f"/notebooks/{self.notebook_id}/edits",
            headers=key(f"edit-{next(self._keys)}"),
            body=json.dumps(
                {
                    "changes": [
                        {
                            "kind": "put_cell",
                            "base_etag": "*",
                            "cell": {"id": self.cells[cell], "code": code},
                        }
                    ]
                }
            ).encode(),
        )
        assert edited.status == 200, edited.body

    async def snapshot(self) -> Snapshot:
        return await snapshot(self.app, self.notebook_id)

    async def outdated(self) -> dict[str, Outdated]:
        """Why each outdated cell is outdated, as a new client sees it."""
        reasons = (await self.snapshot()).outdated()
        return {
            name: reasons[cell_id]
            for name, cell_id in self.cells.items()
            if cell_id in reasons
        }


@contextlib.asynccontextmanager
async def client(
    tmp_path: Path, *, on_cell_change: OnCellChangeType, **cells: str
) -> AsyncIterator[Client]:
    """Serve a notebook of the named cells and connect to it."""
    async with open_host(
        tmp_path, notebook(*cells.values()), on_cell_change=on_cell_change
    ) as (app, notebook_id, events):
        host = app.state.host_context.bridge.host
        document = (await host.notebook(notebook_id)).document
        ids = dict(zip(cells, (cell.id for cell in document), strict=True))
        yield Client(app, notebook_id, events, ids)


# Passes once the host publishes variables and dependencies.
unpublished = pytest.mark.xfail(
    strict=True, reason="the host does not publish variables yet"
)


@unpublished
async def test_edits_and_reruns_outdate_dependents(tmp_path: Path) -> None:
    async with client(
        tmp_path, on_cell_change="lazy", x="x = 1", y="y = x + 1"
    ) as c:
        await c.run("x", "y")
        assert await c.outdated() == {}

        await c.edit("x", "x = 2")
        assert await c.outdated() == {"x": "edited", "y": "edited"}

        await c.run("x")
        assert await c.outdated() == {"y": "replaced"}

        await c.run("y")
        assert await c.outdated() == {}


async def test_autorun_leaves_every_result_current(tmp_path: Path) -> None:
    async with client(
        tmp_path, on_cell_change="autorun", x="x = 1", y="y = x + 1"
    ) as c:
        await c.run("x", "y")
        await c.edit("x", "x = 2")
        await c.run("x")
        assert await c.outdated() == {}


@unpublished
async def test_state_updates_outdate_readers(tmp_path: Path) -> None:
    async with client(
        tmp_path,
        on_cell_change="lazy",
        mo="import marimo as mo",
        state="get_x, set_x = mo.state(1)",
        reader="y = get_x() + 1",
    ) as c:
        await c.run("mo", "state", "reader")
        assert await c.outdated() == {}

        await c.run(code="set_x(2)")
        assert await c.outdated() == {"reader": "updated"}

        await c.run("reader")
        assert await c.outdated() == {}


async def test_state_updates_rerun_readers_in_autorun(tmp_path: Path) -> None:
    async with client(
        tmp_path,
        on_cell_change="autorun",
        mo="import marimo as mo",
        state="get_x, set_x = mo.state(1)",
        reader="y = get_x() + 1",
    ) as c:
        await c.run("mo", "state", "reader")
        await c.run(code="set_x(2)")
        assert await c.outdated() == {}


async def test_a_setter_that_reads_its_own_update_is_current(
    tmp_path: Path,
) -> None:
    async with client(
        tmp_path,
        on_cell_change="lazy",
        mo="import marimo as mo",
        state="get_x, set_x = mo.state(1)",
        setter="for _ in range(3):\n    set_x(get_x() + 1)\nz = get_x()",
    ) as c:
        await c.run("mo", "state", "setter")
        assert await c.outdated() == {}


async def test_reimporting_keeps_dependents_current(tmp_path: Path) -> None:
    async with client(
        tmp_path,
        on_cell_change="autorun",
        imports="import math",
        value="value = math.pi",
    ) as c:
        await c.run("imports", "value")
        before = (await c.snapshot()).latest(c.cells["value"])

        await c.edit("imports", "import math\nimport os")
        await c.run("imports")
        assert await c.outdated() == {}
        # The dependent did not run again, so its result predates the edit.
        assert (await c.snapshot()).latest(c.cells["value"]) == before


@unpublished
async def test_binding_a_missing_name_outdates_its_readers(
    tmp_path: Path,
) -> None:
    async with client(
        tmp_path,
        on_cell_change="lazy",
        binder="pass",
        reader="y = missing + 1",
    ) as c:
        await c.run("binder", "reader")
        assert await c.outdated() == {}

        await c.edit("binder", "missing = 1")
        await c.run("binder")
        assert await c.outdated() == {"reader": "replaced"}
