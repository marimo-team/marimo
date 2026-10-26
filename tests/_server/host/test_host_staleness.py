# Copyright 2026 Marimo. All rights reserved.
"""Clients derive whether results are current from a real host's stream."""

from __future__ import annotations

import contextlib
import itertools
import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import pytest
from msgspec.structs import replace

from marimo._runtime.commands import UpdateUIElementCommand
from tests._server.host.drive import finished, wait_for
from tests._server.host.live import key, open_host
from tests._server.host.staleness import Snapshot, read_events, snapshot

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path

    from starlette.applications import Starlette

    from marimo._config.config import OnCellChangeType
    from marimo._core.protocol import RunOutcome
    from tests._server.host.drive import Response
    from tests._server.host.staleness import Outdated


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

    async def run(
        self,
        *cells: str,
        code: str | None = None,
        outcome: RunOutcome = "succeeded",
    ) -> None:
        """Run the named cells, or code in the scratchpad, to `outcome`."""
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

        def completed(response: Response) -> list[dict[str, Any]]:
            return [
                run
                for r in response.records
                if (run := r.get("data", {}).get("run", {})).get("id")
                == run_id
                and run["status"] == "completed"
            ]

        await wait_for(self.events, lambda response: bool(completed(response)))
        assert completed(self.events)[-1]["outcome"] == outcome

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
        """Compare a connected client with a fresh snapshot."""
        fresh = await self.snapshot()
        live = Snapshot.decode(self.events.records)
        assert live == fresh
        reasons = live.outdated()
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


async def test_variables_outlive_the_run_that_bound_them(
    tmp_path: Path,
) -> None:
    async with client(
        tmp_path,
        on_cell_change="lazy",
        mo="import marimo as mo",
        state="get_x, set_x = mo.state(1)\nif False:\n    missing = 1",
    ) as c:
        await c.run("mo", "state")
        before = await c.snapshot()
        assert {v.name for v in before.variables.values()} == {
            "mo",
            "get_x",
            "set_x",
        }
        getter = next(
            v for v in before.variables.values() if v.name == "get_x"
        )
        execution = before.latest(c.cells["state"])
        assert execution is not None
        assert getter.execution_id == getter.revision.execution == execution.id
        records = c.events.records
        bound = next(
            i
            for i, r in enumerate(records)
            if r.get("event") == "variable"
            and r["data"]["variable"]["id"] == getter.id
        )
        completed = next(
            i
            for i, r in enumerate(records)
            if r.get("event") == "execution"
            and r["data"]["execution"]["id"] == execution.id
            and r["data"]["execution"]["status"] == "completed"
        )
        assert bound < completed

        await c.run(code="local_only = 10\nget_x = 'scratch-local'\nset_x(2)")
        after = await c.snapshot()
        assert {v.name for v in after.variables.values()} == {
            "mo",
            "get_x",
            "set_x",
        }
        assert next(
            v for v in after.variables.values() if v.name == "get_x"
        ) == replace(
            getter,
            revision=replace(getter.revision, update=1),
        )


async def test_edits_and_reruns_outdate_dependents(tmp_path: Path) -> None:
    async with client(
        tmp_path,
        on_cell_change="lazy",
        x="x = 1",
        y="y = x + 1",
        z="z = y + 1",
    ) as c:
        await c.run("x", "y", "z")
        initial = await c.snapshot()
        x = next(v for v in initial.variables.values() if v.name == "x")
        y = initial.latest(c.cells["y"])
        assert y is not None
        assert y.depends_on == {"x": x.revision}
        assert await c.outdated() == {}

        await c.edit("x", "x = 2")
        assert await c.outdated() == {
            "x": "edited",
            "y": "edited",
            "z": "edited",
        }

        await c.run("x")
        assert await c.outdated() == {"y": "replaced", "z": "replaced"}

        await c.run("y")
        assert await c.outdated() == {"z": "replaced"}

        await c.run("z")
        assert await c.outdated() == {}


async def test_autorun_leaves_every_result_current(tmp_path: Path) -> None:
    async with client(
        tmp_path, on_cell_change="autorun", x="x = 1", y="y = x + 1"
    ) as c:
        await c.run("x", "y")
        await c.edit("x", "x = 2")
        await c.run("x")
        current = await c.snapshot()
        x = next(v for v in current.variables.values() if v.name == "x")
        y = current.latest(c.cells["y"])
        assert y is not None
        assert y.depends_on == {"x": x.revision}
        assert await c.outdated() == {}


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
        current = await c.snapshot()
        getter = next(
            v for v in current.variables.values() if v.name == "get_x"
        )
        reader = current.latest(c.cells["reader"])
        assert reader is not None
        assert getter.revision.update == 1
        assert reader.depends_on == {"get_x": getter.revision}
        records = c.events.records
        updated = next(
            i
            for i, r in enumerate(records)
            if r.get("event") == "variable"
            and r["data"]["variable"]["id"] == getter.id
            and r["data"]["variable"]["revision"]["update"] == 1
        )
        dependent = next(
            i
            for i, r in enumerate(records)
            if r.get("event") == "execution"
            and r["data"]["execution"]["id"] == reader.id
        )
        assert updated < dependent
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
        current = await c.snapshot()
        getter = next(
            v for v in current.variables.values() if v.name == "get_x"
        )
        setter = current.latest(c.cells["setter"])
        assert setter is not None
        assert getter.revision.update == 3
        assert setter.depends_on["get_x"] == getter.revision
        assert await c.outdated() == {}


async def test_reimporting_keeps_dependents_current(tmp_path: Path) -> None:
    async with client(
        tmp_path,
        on_cell_change="autorun",
        imports="import math",
        value="value = math.pi",
    ) as c:
        await c.run("imports", "value")
        initial = await c.snapshot()
        before = initial.latest(c.cells["value"])
        math = next(v for v in initial.variables.values() if v.name == "math")
        assert before is not None
        assert before.depends_on == {"math": math.revision}

        await c.edit("imports", "import math\nimport os")
        await c.run("imports")
        current = next(
            v
            for v in (await c.snapshot()).variables.values()
            if v.name == "math"
        )
        assert current.revision == math.revision
        assert current.execution_id != math.execution_id
        assert await c.outdated() == {}
        # The dependent did not run again, so its result predates the edit.
        assert (await c.snapshot()).latest(c.cells["value"]) == before


@pytest.mark.parametrize(
    ("name", "expression", "binding", "outcome"),
    [
        ("missing", "missing + 1", "missing = 1", "failed"),
        ("len", "len([1])", "len = lambda _: 2", "succeeded"),
        ("print", "print('old')", "print = lambda _: None", "succeeded"),
    ],
)
async def test_binding_a_name_outdates_its_unbound_readers(
    tmp_path: Path,
    name: str,
    expression: str,
    binding: str,
    outcome: RunOutcome,
) -> None:
    async with client(
        tmp_path,
        on_cell_change="lazy",
        binder="pass",
        reader=f"y = {expression}",
    ) as c:
        if name == "print":
            # A thread installs print in globals without a notebook binding.
            await c.run(
                code="import marimo as mo\nt = mo.Thread(target=lambda: None)\nt.start()\nt.join()"
            )
        await c.run("binder", "reader", outcome=outcome)
        reader = (await c.snapshot()).latest(c.cells["reader"])
        assert reader is not None
        assert reader.depends_on == {name: None}
        assert await c.outdated() == {}

        await c.edit("binder", binding)
        await c.run("binder")
        assert await c.outdated() == {"reader": "replaced"}


async def test_replaced_inputs_take_precedence_over_updates_and_edits(
    tmp_path: Path,
) -> None:
    async with client(
        tmp_path,
        on_cell_change="lazy",
        mo="import marimo as mo",
        state="get_x, set_x = mo.state(1)",
        x="x = 1",
        reader="y = get_x() + x",
    ) as c:
        await c.run("mo", "state", "x", "reader")
        await c.edit("reader", "y = get_x() + x + 1")
        assert await c.outdated() == {"reader": "edited"}

        await c.run(code="set_x(2)")
        assert await c.outdated() == {"reader": "updated"}

        await c.run("x")
        assert await c.outdated() == {"reader": "replaced"}


@pytest.mark.parametrize(
    ("code", "outcome"),
    [("if False:\n    x = 2", "succeeded"), ("1 / 0\nx = 2", "failed")],
)
async def test_a_rerun_that_does_not_bind_a_name_outdates_its_readers(
    tmp_path: Path,
    code: str,
    outcome: RunOutcome,
) -> None:
    async with client(
        tmp_path,
        on_cell_change="lazy",
        binder="x = 1",
        reader="y = x + 1",
    ) as c:
        await c.run("binder", "reader")
        await c.edit("binder", code)
        await c.run("binder", outcome=outcome)
        assert "x" not in {
            v.name for v in (await c.snapshot()).variables.values()
        }
        assert await c.outdated() == {"reader": "replaced"}

        await c.run("reader", outcome="failed")
        reader = (await c.snapshot()).latest(c.cells["reader"])
        assert reader is not None
        assert reader.depends_on == {"x": None}
        assert await c.outdated() == {}


async def test_a_ui_update_outdates_lazy_readers(tmp_path: Path) -> None:
    async with client(
        tmp_path,
        on_cell_change="lazy",
        mo="import marimo as mo",
        slider="slider = mo.ui.slider(0, 10, value=1)",
        reader="value = slider.value",
    ) as c:
        await c.run("mo", "slider", "reader")
        before = await c.snapshot()
        slider = next(
            v for v in before.variables.values() if v.name == "slider"
        )
        start = len(c.events.records)
        await c.run(code="print(slider._id)")
        [object_id] = [
            r["data"]["console"]["text"].strip()
            for r in c.events.records[start:]
            if r.get("event") == "console"
            and r["data"]["console"]["text"].strip()
        ]
        session = next(iter(c.app.state.session_manager.sessions.values()))
        session.put_control_request(
            UpdateUIElementCommand.from_ids_and_values([(object_id, 5)]),
            from_consumer_id=None,
        )
        await wait_for(
            c.events,
            lambda response: any(
                r.get("event") == "variable"
                and r["data"]["variable"]["id"] == slider.id
                and r["data"]["variable"]["revision"]["update"] == 1
                for r in response.records
            ),
        )
        after = await c.snapshot()
        assert after.variables[slider.id] == replace(
            slider, preview="5", revision=replace(slider.revision, update=1)
        )
        assert after.latest(c.cells["reader"]) == before.latest(
            c.cells["reader"]
        )
        assert await c.outdated() == {"reader": "updated"}


async def test_state_updates_precede_nested_readers(tmp_path: Path) -> None:
    async with client(
        tmp_path,
        on_cell_change="lazy",
        mo="import marimo as mo",
        state="get_x, set_x = mo.state(1)",
        reader="y = get_x()",
    ) as c:
        await c.run("mo", "state", "reader")
        offset = len(c.events.records)
        await c.run(
            code=(
                "set_x(2)\nimport marimo._code_mode as cm\n"
                "async with cm.get_context() as ctx:\n"
                f"    ctx.run_cell({c.cells['reader']!r})"
            )
        )
        records = c.events.records[offset:]
        updated = next(
            i
            for i, r in enumerate(records)
            if r.get("event") == "variable"
            and r["data"]["variable"]["name"] == "get_x"
        )
        started = next(
            i
            for i, r in enumerate(records)
            if r.get("event") == "execution"
            and r["data"]["execution"]["cell_id"] == c.cells["reader"]
            and r["data"]["execution"]["status"] == "running"
        )
        assert updated < started
        current = await c.snapshot()
        getter = next(
            v for v in current.variables.values() if v.name == "get_x"
        )
        reader = current.latest(c.cells["reader"])
        assert reader is not None
        assert reader.depends_on == {"get_x": getter.revision}
        assert getter.revision.update == 1
        assert await c.outdated() == {}


async def test_reconnecting_recovers_updates_and_replaced_bindings(
    tmp_path: Path,
) -> None:
    async with client(
        tmp_path,
        on_cell_change="lazy",
        mo="import marimo as mo",
        state="get_x, set_x = mo.state(1)",
        x="x = 1",
        reader="y = get_x() + x",
    ) as c:
        await c.run("mo", "state", "x", "reader")
        initial = await read_events(c.app, c.notebook_id)
        cursor = initial[-1]["id"]
        assert Snapshot.decode(initial).outdated() == {}

        await c.run(code="set_x(2)")
        await c.edit("x", "x = 2")
        await c.run("x")

        replay = await read_events(c.app, c.notebook_id, cursor=cursor)
        assert "reset" not in {r["event"] for r in replay}
        recovered = Snapshot.decode([*initial, *replay])
        assert (
            recovered
            == Snapshot.decode(c.events.records)
            == await c.snapshot()
        )
        assert recovered.outdated() == {c.cells["reader"]: "replaced"}
