# Copyright 2026 Marimo. All rights reserved.
"""Kernel commands and updates for the host API.

```python
notebook = host.add_notebook(record, backend)
notebook.start()  # Calls backend.start(...).

# The backend reports kernel startup through Notebook.observe.
notebook.observe(Starting("Launching kernel"))
notebook.observe(Running())
```

marimo currently manages sessions and kernels outside the core model.
A backend lets the host API run as a sidecar, reporting activity from
both API commands and existing clients. The adapter may become
unnecessary if marimo adopts the core model directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from marimo._core import protocol


class Backend(Protocol):
    """Commands for managing a notebook's kernel.

    Commands return without waiting for completion. Implementations report
    updates through `Notebook.observe` and assign execution and item IDs.
    """

    def start(self, runtime_id: protocol.RuntimeId) -> None:
        """Start a kernel for the given runtime.

        Report `Starting` while launching, then `Running` on success or
        `Exited` with a reason on failure.
        """

    def stop(self) -> None:
        """Stop the kernel and report `Exited` when shutdown completes."""

    def run(self, run_id: protocol.RunId, code: str) -> None:
        """Evaluate scratch code and report the run's progress and output."""

    def interrupt(self, run_id: protocol.RunId) -> None:
        """Interrupt a run and report an `interrupted` execution outcome."""


# Runtime lifecycle


@dataclass(frozen=True)
class Starting:
    """Kernel startup progress, with an optional status message."""

    message: str | None = None


@dataclass(frozen=True)
class Running:
    """The kernel is ready to execute code."""

    marimo_version: str | None = None


@dataclass(frozen=True)
class Exited:
    """The kernel stopped or exited unexpectedly."""

    reason: str | None = None


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
    """An execution's current outcome; final once the execution is completed."""

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
