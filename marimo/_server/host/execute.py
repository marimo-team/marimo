# Copyright 2026 Marimo. All rights reserved.
"""Runs code on a notebook's runtime for a client.

The code runs in the kernel's scratchpad, and what the kernel reports
becomes observations for the host. One execution runs at a time per
notebook.
"""

from __future__ import annotations

import asyncio
import html
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from marimo import _loggers
from marimo._host.model import ConsoleLine, Display, ExecutionError
from marimo._host.transitions import (
    ExecutionEnded,
    ExecutionForgotten,
    ExecutionPrinted,
    ExecutionShown,
    ExecutionStarted,
)
from marimo._messaging.cell_output import CellChannel
from marimo._messaging.errors import (
    MarimoExceptionRaisedError,
    MarimoInterruptionError,
    MarimoSyntaxError,
    UnknownError,
)
from marimo._messaging.tracebacks import is_code_highlighting
from marimo._runtime.commands import ExecuteScratchpadCommand, HTTPRequest
from marimo._runtime.scratch import SCRATCH_CELL_ID
from marimo._server.scratchpad import (
    ScratchCellListener,
    snapshot_for_scratchpad,
)
from marimo._session.requests import InstantiateNotebookRequest

if TYPE_CHECKING:
    from marimo._host.host import Host
    from marimo._host.model import FinalStatus
    from marimo._messaging.errors import Error
    from marimo._messaging.notification import CellNotification
    from marimo._session.types import Session
    from marimo._types.ids import ExecutionId, NotebookId

LOGGER = _loggers.marimo_logger()

RETENTION_SECONDS = 60.0
"""How long a finished execution stays before the host forgets it."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Run:
    """One execution in progress."""

    id: ExecutionId
    notebook_id: NotebookId
    session: Session
    task: asyncio.Task[None] | None = None
    interrupted: bool = False

    def interrupt(self) -> None:
        """Asks the kernel to stop. The execution then ends `interrupted`."""
        if self.interrupted:
            return
        self.interrupted = True
        self.session.try_interrupt()


@dataclass
class Executions:
    """The runs in progress, by execution id."""

    running: dict[ExecutionId, Run] = field(default_factory=dict)

    def start(
        self,
        host: Host,
        session: Session,
        *,
        notebook_id: NotebookId,
        execution_id: ExecutionId,
        code: str,
        http_request: HTTPRequest,
    ) -> Run:
        """Begins running `code`, which the host has already queued."""
        run = Run(execution_id, notebook_id, session)
        self.running[execution_id] = run
        run.task = asyncio.get_running_loop().create_task(
            _run(self, host, run, code, http_request),
            name=f"host.execute.{execution_id}",
        )
        return run

    def abandon(self, notebook_id: NotebookId) -> None:
        """Stops following the notebook's runs, as when its kernel goes."""
        for run in list(self.running.values()):
            if run.notebook_id == notebook_id and run.task is not None:
                run.task.cancel()


async def _run(
    executions: Executions,
    host: Host,
    run: Run,
    code: str,
    http_request: HTTPRequest,
) -> None:
    key = run.id
    session = run.session
    listener = ScratchCellListener(run_id=key)
    errors: list[Error] = []
    started = False

    def report(observation) -> None:  # type: ignore[no-untyped-def]
        host.observe(observation, request_id=key)

    try:
        # Registers cells without running them, so the code can see the
        # notebook's definitions. A no-op once the kernel is instantiated.
        session.instantiate(
            InstantiateNotebookRequest(
                object_ids=[], values=[], auto_run=False
            ),
            http_request=http_request,
        )
        async with session.scratchpad_lock:
            with session.scoped(listener):
                if run.interrupted:
                    # Interrupted before anything was submitted; there is
                    # nothing in the kernel to stop.
                    report(
                        ExecutionEnded(
                            run.notebook_id, key, "interrupted", (), _utcnow()
                        )
                    )
                    return
                notebook_cells, cell_outputs = snapshot_for_scratchpad(session)
                session.put_control_request(
                    ExecuteScratchpadCommand(
                        code=code,
                        request=http_request,
                        notebook_cells=notebook_cells,
                        cell_outputs=cell_outputs,
                        run_id=key,
                    ),
                    from_consumer_id=None,
                )
                async for message in listener.notifications():
                    if message is None:
                        continue
                    # `running` is reported when the kernel says the cell
                    # is running, not when the command is queued: an
                    # interrupt sent to an idle kernel is lost, and a
                    # client interrupts as soon as it sees this.
                    if (
                        not started
                        and message.cell_id == SCRATCH_CELL_ID
                        and message.status == "running"
                    ):
                        started = True
                        report(
                            ExecutionStarted(run.notebook_id, key, _utcnow())
                        )
                        if run.interrupted:
                            # Asked before the kernel got going; ask again
                            # now that there is something to stop.
                            session.try_interrupt()
                    for line in _printed(message):
                        report(ExecutionPrinted(run.notebook_id, key, line))
                    if message.cell_id != SCRATCH_CELL_ID:
                        continue
                    shown, failed = _shown(message)
                    if shown is not None:
                        report(ExecutionShown(run.notebook_id, key, shown))
                    errors.extend(failed)
        report(
            ExecutionEnded(
                run.notebook_id,
                key,
                _status(run, errors),
                tuple(_describe(e) for e in errors),
                _utcnow(),
            )
        )
    except asyncio.CancelledError:
        # The runtime is going away; the host has said what that means
        # for the execution, so there is nothing to report here.
        raise
    except Exception as e:
        LOGGER.exception("Execution %s failed in the host", key)
        report(
            ExecutionEnded(
                run.notebook_id,
                key,
                "failed",
                (ExecutionError("internal", None, str(e), None),),
                _utcnow(),
            )
        )
    finally:
        executions.running.pop(key, None)
        # A finished execution stays for a while, so a client that lost
        # its connection can still find the result. Then it goes.
        try:
            asyncio.get_running_loop().call_later(
                RETENTION_SECONDS,
                lambda: host.observe(ExecutionForgotten(run.notebook_id, key)),
            )
        except RuntimeError:
            pass


def _status(run: Run, errors: list[Error]) -> FinalStatus:
    if run.interrupted or any(
        isinstance(e, MarimoInterruptionError) for e in errors
    ):
        return "interrupted"
    return "failed" if errors else "succeeded"


def _printed(message: CellNotification) -> list[ConsoleLine]:
    """Text printed while this notification's cell ran.

    Includes other cells the code triggered, since their output is part
    of the run.
    """
    if message.console is None:
        return []
    entries = (
        message.console
        if isinstance(message.console, list)
        else [message.console]
    )
    lines: list[ConsoleLine] = []
    for entry in entries:
        if entry is None:
            continue
        if entry.channel == CellChannel.STDOUT:
            lines.append(ConsoleLine("stdout", _plain(str(entry.data))))
        elif entry.channel == CellChannel.STDERR:
            lines.append(ConsoleLine("stderr", _plain(str(entry.data))))
    return lines


def _plain(text: str) -> str:
    """Console text as printed, with any syntax highlighting removed."""
    if not is_code_highlighting(text):
        return text
    return html.unescape(re.sub(r"<[^>]+>", "", text))


def _shown(message: CellNotification) -> tuple[Display | None, list[Error]]:
    """The scratch cell's output as a display, or the errors it raised."""
    output = message.output
    if output is None:
        return None, []
    if output.channel == CellChannel.MARIMO_ERROR:
        return None, list(output.data) if isinstance(output.data, list) else []
    if output.channel != CellChannel.OUTPUT:
        return None, []
    data = output.data
    text = data if isinstance(data, str) else json.dumps(data)
    return Display(mimetype=str(output.mimetype), data=text), []


def _describe(error: Error) -> ExecutionError:
    if isinstance(error, MarimoExceptionRaisedError):
        return ExecutionError(
            "exception", error.exception_type, error.msg, error.traceback
        )
    if isinstance(error, MarimoSyntaxError):
        return ExecutionError("syntax", None, error.msg, None)
    if isinstance(error, MarimoInterruptionError):
        return ExecutionError("interruption", None, error.describe(), None)
    if isinstance(error, UnknownError):
        return ExecutionError("internal", error.error_type, error.msg, None)
    return ExecutionError("internal", None, error.describe(), None)
