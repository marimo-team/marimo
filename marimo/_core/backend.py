# Copyright 2026 Marimo. All rights reserved.
"""Kernel commands and updates for the host API.

```python
notebook = Notebook(notebook_id, document, Executions(), backend, sink)
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

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol

from marimo._core import protocol

if TYPE_CHECKING:
    from collections.abc import Sequence

    from marimo._core.document import Document


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
        """Evaluate scratch code and report the run's progress and output.

        Runs are handed over in acceptance order and reach the kernel in
        that order, however long each takes to prepare.
        """

    def run_cells(
        self,
        run_id: protocol.RunId,
        document: Document,
        cell_ids: Sequence[protocol.CellId],
    ) -> None:
        """Run cells of `document` and report the run's progress and output.

        Handed over like `run`, with the document the run was accepted in.
        Requested cells and pending ancestors are registered before
        execution. Dependent cells follow the runtime's execution
        configuration. Each execution reports the fingerprint submitted
        with its cell.
        """

    def interrupt(self, run_id: protocol.RunId) -> None:
        """End a run and report its `interrupted` outcome.

        A run the kernel has not started completes without running. One
        the kernel could not stop at once is stopped as it progresses.
        """

    def update_ui_element(
        self,
        element_id: str,
        state: protocol.UIElementPartialState,
        request_id: str,
    ) -> None:
        """Apply state and report the kernel's value with the request identity."""

    def forget(self, run_id: protocol.RunId) -> None:
        """Release a run the host no longer retains.

        Later kernel messages for the run are dropped.
        """

    def send_ui_element(
        self,
        element_id: str,
        message: protocol.UIElementFunctionCall,
        call_id: str,
    ) -> None:
        """Invoke a registered function and report its caller-only result."""


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


@dataclass(frozen=True)
class PlannedExecution:
    id: protocol.ExecutionId
    cell_id: str | None
    code_fingerprint: str
    code: str | None
    caused_by: protocol.ExecutionId | None = None


@dataclass(frozen=True)
class Planned:
    """A run's planned executions, reported before any execution starts."""

    run_id: protocol.RunId
    executions: tuple[PlannedExecution, ...]


@dataclass(frozen=True)
class Started:
    """An execution started evaluating code."""

    execution_id: protocol.ExecutionId


@dataclass(frozen=True)
class Completed:
    """An execution finished with its final outcome and input revisions."""

    execution_id: protocol.ExecutionId
    outcome: protocol.Outcome
    depends_on: dict[str, protocol.Revision | None] = field(
        default_factory=dict
    )


@dataclass(frozen=True)
class Produced:
    """An item produced by an execution.

    Reusing an item ID replaces its previous value.
    """

    item: protocol.Console | protocol.Display | protocol.Variable


@dataclass(frozen=True)
class Unbound:
    """A variable removed from the namespace, identified by its producer."""

    execution_id: protocol.ExecutionId
    name: str


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


@dataclass(frozen=True)
class UIElementCreated:
    """A UI element created by the current runtime."""

    runtime_id: protocol.RuntimeId
    element: protocol.UIElement


@dataclass(frozen=True)
class UIElementsRemoved:
    """The current runtime invalidated a cell's UI elements."""

    runtime_id: protocol.RuntimeId
    cell_id: protocol.CellId


@dataclass(frozen=True)
class UIElementUpdated:
    runtime_id: protocol.RuntimeId
    element_id: str
    state: protocol.UIElementPartialState
    request_id: str | None


@dataclass(frozen=True)
class UIElementResult:
    """A function reply, never retained or published on the shared stream."""

    runtime_id: protocol.RuntimeId
    call_id: str
    result: protocol.UIElementFunctionResult


Message = (
    Starting
    | Running
    | Exited
    | Scheduled
    | Planned
    | Started
    | Completed
    | Produced
    | Unbound
    | Concluded
    | Done
    | UIElementCreated
    | UIElementsRemoved
    | UIElementUpdated
    | UIElementResult
)
