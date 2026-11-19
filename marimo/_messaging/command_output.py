# Copyright 2026 Marimo. All rights reserved.
"""Route console writes made by an editor command to its cell."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING
from uuid import uuid4

import msgspec

from marimo._messaging.context import (
    EXECUTION_CTX,
    RUN_ID_CTX,
    ExecutionTag,
    execution_id_for,
)
from marimo._messaging.notification import (
    CallbackOutputNotification,
    CellNotification,
    PdbOutputNotification,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from marimo._ast.cell import RuntimeStateType
    from marimo._messaging.cell_output import CellOutput
    from marimo._types.ids import CellId_t

CommandOutput = type[CallbackOutputNotification] | type[PdbOutputNotification]
_destination: ContextVar[tuple[CellId_t, CommandOutput] | None] = ContextVar(
    "command_console", default=None
)


@dataclass(frozen=True)
class ConsoleContext:
    """The notebook operation that owns a background writer's output."""

    run_id: str | None = field(default_factory=lambda: RUN_ID_CTX.get(None))
    execution: ExecutionTag | None = field(default_factory=EXECUTION_CTX.get)
    command: tuple[CellId_t, CommandOutput] | None = field(
        default_factory=_destination.get
    )

    def for_native_writer(self) -> ConsoleContext:
        # Reading bytes only needs the execution id. A child can outlive the
        # evaluation, including its source and dependency metadata.
        if self.execution is None:
            return self
        return replace(self, execution=replace(self.execution, attempt=None))

    @contextmanager
    def install(self) -> Iterator[None]:
        run = RUN_ID_CTX.set(self.run_id)
        execution = EXECUTION_CTX.set(self.execution)
        destination = _destination.set(self.command)
        try:
            yield
        finally:
            _destination.reset(destination)
            EXECUTION_CTX.reset(execution)
            RUN_ID_CTX.reset(run)


@contextmanager
def command_console(
    cell_id: CellId_t, output: CommandOutput
) -> Iterator[None]:
    token = _destination.set((cell_id, output))
    try:
        yield
    finally:
        _destination.reset(token)


def destination_for(cell_id: CellId_t) -> CommandOutput | None:
    destination = _destination.get()
    if (
        destination
        and destination[0] == cell_id
        and execution_id_for(cell_id) is None
    ):
        return destination[1]
    return None


def console_notification(
    cell_id: CellId_t,
    console: CellOutput | list[CellOutput],
    *,
    run_id: str | None = None,
    execution_id: str | None = None,
    destination: CommandOutput | msgspec.UnsetType | None = msgspec.UNSET,
    status: RuntimeStateType | None = None,
) -> CellNotification | CallbackOutputNotification | PdbOutputNotification:
    output = (
        destination_for(cell_id)
        if destination is msgspec.UNSET
        else destination
    )
    if output is not None and execution_id is None and status is None:
        entries = console if isinstance(console, list) else [console]
        return output(
            cell_id,
            [
                msgspec.structs.replace(entry, command_id=uuid4().hex)
                for entry in entries
            ],
        )
    return CellNotification(
        cell_id=cell_id,
        console=console,
        run_id=run_id,
        execution_id=execution_id,
        status=status,
    )
