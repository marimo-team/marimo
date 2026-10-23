# Copyright 2026 Marimo. All rights reserved.
"""A client's derivation of which results are current, as the spec states it.

See "Runs and results" in `protocols/host/spec.md`.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

import msgspec

from marimo._core import protocol
from tests._server.host.drive import request, wait_for
from tests._server.host.live import AUTH

if TYPE_CHECKING:
    from typing import Any

    from starlette.applications import Starlette

Outdated = Literal["replaced", "updated", "edited"]
"""Why a result is outdated. When several apply, the first listed wins."""

_ORDER: tuple[Outdated, ...] = ("replaced", "updated", "edited")


@dataclass(frozen=True)
class Snapshot:
    """The cells, executions, and variables a client holds."""

    cells: dict[str, protocol.Cell]
    executions: dict[str, protocol.Execution]
    variables: tuple[protocol.Variable, ...]

    @classmethod
    def decode(cls, records: list[dict[str, Any]]) -> Snapshot:
        cells: dict[str, protocol.Cell] = {}
        executions: dict[str, protocol.Execution] = {}
        variables: list[protocol.Variable] = []
        for record in records:
            event = record.get("event")
            raw = msgspec.json.encode(record.get("data"))
            if event == "cell":
                cell = msgspec.json.decode(raw, type=protocol.CellMessage).cell
                cells[cell.id] = cell
            elif event == "execution":
                execution = msgspec.json.decode(
                    raw, type=protocol.ExecutionMessage
                ).execution
                executions[execution.id] = execution
            elif event == "variable":
                variables.append(
                    msgspec.json.decode(
                        raw, type=protocol.VariableMessage
                    ).variable
                )
        return cls(cells, executions, tuple(variables))

    def latest(self, cell_id: str) -> protocol.Execution | None:
        """The cell's completed execution, if it has one."""
        return next(
            (
                execution
                for execution in self.executions.values()
                if execution.cell_id == cell_id
                and execution.status == "completed"
            ),
            None,
        )

    def outdated(self) -> dict[str, Outdated]:
        """Why each outdated cell's result is outdated, by cell id.

        Cells whose result is current, or that have no result to compare,
        are omitted.
        """
        reasons: dict[str, Outdated] = {}
        for cell_id in self.cells:
            execution = self.latest(cell_id)
            reason = None if execution is None else self._reason(execution)
            if reason is not None:
                reasons[cell_id] = reason
        return reasons

    def _reason(self, execution: protocol.Execution) -> Outdated | None:
        assert execution.cell_id is not None
        reasons = [
            reason
            for name, revision in execution.depends_on.items()
            if (reason := self._dependency(name, revision)) is not None
        ]
        if execution.code_hash != self.cells[execution.cell_id].code_hash:
            reasons.append("edited")
        return min(reasons, key=_ORDER.index, default=None)

    def _dependency(
        self, name: str, revision: protocol.Revision | None
    ) -> Outdated | None:
        if revision is None:
            bound = any(v.name == name for v in self.variables)
            return "replaced" if bound else None
        variable = next(
            (
                v
                for v in self.variables
                if v.name == name
                and v.revision.execution == revision.execution
            ),
            None,
        )
        if variable is None:
            return "replaced"
        if variable.revision.update != revision.update:
            return "updated"
        return self._reason(self.executions[variable.execution_id])


async def snapshot(app: Starlette, notebook_id: str) -> Snapshot:
    """Connect as a new client and read the notebook's state."""
    response, task, disconnect = request(
        app, "GET", f"/notebooks/{notebook_id}/events", headers=AUTH
    )
    try:
        await wait_for(response, lambda r: "ready" in r.names())
    finally:
        disconnect()
        await asyncio.wait_for(task, 5)
    ready = response.names().index("ready")
    return Snapshot.decode(
        [r for r in response.records if "event" in r][:ready]
    )
