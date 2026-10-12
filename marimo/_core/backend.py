# Copyright 2026 Marimo. All rights reserved.
"""Kernel commands and updates for the host API.

```python
notebook = Notebook(document, Executions(), backend, sink)
runtime, _ = notebook.start()  # Calls backend.start(runtime.id).

# The backend reports on that runtime through Notebook.observe.
notebook.observe(Starting(runtime.id, "Launching kernel"))
notebook.observe(Running(runtime.id))
```

marimo currently manages sessions and kernels outside the core model.
A backend lets the host API run as a sidecar, reporting activity from
both API commands and existing clients. The adapter may become
unnecessary if marimo adopts the core model directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from marimo._core import protocol

if TYPE_CHECKING:
    from collections.abc import Sequence


class Backend(Protocol):
    """Commands for managing a notebook's kernel.

    Commands return without waiting for completion. Implementations report
    updates through `Notebook.observe` and assign execution and item IDs.
    Runtime reports name the runtime they concern, so a report from a
    kernel the notebook no longer tracks is ignored.
    """

    def start(self, runtime_id: protocol.RuntimeId) -> None:
        """Start a kernel for the given runtime.

        Report `Starting` while launching, then `Running` on success or
        `Exited` with a reason on failure.
        """

    def stop(self, runtime_id: protocol.RuntimeId) -> None:
        """Stop the runtime's kernel and report `Exited` once it has."""

    def run(self, run_id: protocol.RunId, code: str) -> None:
        """Evaluate scratch code and report the run's progress and output."""

    def run_cells(
        self, run_id: protocol.RunId, cells: Sequence[protocol.Cell]
    ) -> None:
        """Run cells of the document, and the cells that depend on them.

        Report each cell's execution with its `cell_id` and no code.
        """

    def interrupt(self, run_id: protocol.RunId) -> None:
        """Interrupt a run and report an `interrupted` execution outcome."""

    def forget(self, run_id: protocol.RunId) -> None:
        """Release a run the host no longer retains.

        Later kernel messages for the run are dropped.
        """


# Runtime reports


@dataclass(frozen=True)
class Starting:
    """Kernel startup progress, with an optional status message."""

    runtime_id: protocol.RuntimeId
    message: str | None = None


@dataclass(frozen=True)
class Running:
    """The kernel is ready to execute code."""

    runtime_id: protocol.RuntimeId
    marimo_version: str | None = None


@dataclass(frozen=True)
class Exited:
    """The kernel stopped or exited unexpectedly."""

    runtime_id: protocol.RuntimeId
    reason: str | None = None


RuntimeReport = Starting | Running | Exited


# Runs


@dataclass(frozen=True)
class Scheduled:
    """The runtime scheduled a run independently of a host API request."""

    run_id: protocol.RunId
    caused_by: protocol.ExecutionId | None = None


@dataclass(frozen=True)
class PlannedExecution:
    id: protocol.ExecutionId
    cell_id: str | None
    code_hash: str
    code: str | None
    caused_by: protocol.ExecutionId | None = None


@dataclass(frozen=True)
class Planned:
    """A run's planned executions, reported before any execution starts."""

    run_id: protocol.RunId
    executions: tuple[PlannedExecution, ...]


@dataclass(frozen=True)
class Status:
    """An execution changed status to `running` or `completed`."""

    execution_id: protocol.ExecutionId
    status: protocol.Lifecycle


@dataclass(frozen=True)
class Produced:
    """Console or display output from an execution.

    Reusing an item ID replaces its previous value.
    """

    item: protocol.Console | protocol.Display


@dataclass(frozen=True)
class Concluded:
    """An execution outcome, final when the execution completes."""

    execution_id: protocol.ExecutionId
    outcome: protocol.Outcome


@dataclass(frozen=True)
class Done:
    """The cycle ended and will schedule no more executions.

    All planned executions must already have a final outcome and status.
    The outcome also accounts for failures or interruption of the cycle
    itself, including termination before any execution was planned.
    """

    run_id: protocol.RunId
    outcome: protocol.RunOutcome


Message = (
    Starting
    | Running
    | Exited
    | Scheduled
    | Planned
    | Status
    | Produced
    | Concluded
    | Done
)
