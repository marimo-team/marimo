# Copyright 2026 Marimo. All rights reserved.
"""Kernel notifications translated into runs and their member executions."""

from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass, field

from marimo._core import backend as be, protocol
from marimo._core.document import code_hash
from marimo._messaging.cell_output import CellChannel
from marimo._messaging.errors import (
    Error,
    MarimoExceptionRaisedError,
    MarimoInterruptionError,
    MarimoSyntaxError,
    UnknownError,
)
from marimo._messaging.notification import (
    CellNotification,
    CompletedRunNotification,
    ExecutionNotification,
    InterruptedNotification,
    NotificationMessage,
)
from marimo._messaging.tracebacks import is_code_highlighting
from marimo._runtime.scratch import SCRATCH_CELL_ID


@dataclass
class _Execution:
    id: protocol.ExecutionId
    cell_id: str
    ended: bool = False
    reported: bool = False
    outcome: protocol.Outcome = field(
        default_factory=lambda: protocol.ValueOutcome(None)
    )
    errors: list[Error] = field(default_factory=list)
    seq: int = 0


class RunTranslator:
    """Track evaluations within one bounded reactive cycle."""

    def __init__(self, run_id: protocol.RunId, code: str | None) -> None:
        self.run_id = run_id
        self._code = code
        self._finished = False
        self.completed = False
        self.interrupted = False
        self._failed = False
        self._error: protocol.Error | None = None
        self._executions: dict[str, _Execution] = {}

    def feed(self, notification: NotificationMessage) -> list[be.Message]:
        """Translate an attempt's lifecycle and output by its kernel identity."""
        if isinstance(notification, InterruptedNotification):
            if notification.run_id == self.run_id and not self._finished:
                self.interrupted = True
            return []
        if isinstance(notification, CompletedRunNotification):
            if notification.run_id == self.run_id and not self._finished:
                self.completed = True
                self.interrupted |= notification.outcome == "interrupted"
                self._failed |= notification.outcome == "failed"
                if notification.error and notification.outcome == "failed":
                    self._error = _describe(UnknownError(notification.error))
            return []
        if not isinstance(
            notification, (CellNotification, ExecutionNotification)
        ):
            return []
        if notification.run_id != self.run_id:
            return []
        if isinstance(notification, ExecutionNotification):
            if self._finished:
                return []
            if notification.phase == "planned":
                if notification.execution_id in self._executions:
                    return []
                return [self._plan(notification)]
            execution = self._executions.get(notification.execution_id)
            if execution is None or execution.ended:
                return []
            if notification.phase == "running":
                return [be.Status(execution.id, "running")]
            return self._conclude(execution)

        execution = self._executions.get(notification.execution_id or "")
        if execution is None:
            return []
        out = self._console(execution, notification)
        if execution.ended or self._finished:
            return out
        if notification.output is not None:
            output = notification.output
            if output.channel == CellChannel.MARIMO_ERROR and isinstance(
                output.data, list
            ):
                execution.errors.extend(output.data)
            elif output.channel == CellChannel.OUTPUT:
                text = (
                    output.data
                    if isinstance(output.data, str)
                    else json.dumps(output.data)
                )
                execution.outcome = protocol.ValueOutcome(
                    None
                    if output.mimetype == "text/plain" and text == ""
                    else protocol.DisplayData(
                        mimetype=str(output.mimetype), data=text
                    )
                )
                execution.reported = True
                out.append(be.Concluded(execution.id, execution.outcome))
        return out

    def _plan(self, notification: ExecutionNotification) -> be.Planned:
        execution = _Execution(
            protocol.ExecutionId(f"{self.run_id}-{len(self._executions) + 1}"),
            notification.cell_id,
        )
        self._executions[notification.execution_id] = execution
        parent = self._executions.get(notification.caused_by or "")
        code = notification.code or ""
        return be.Planned(
            self.run_id,
            (
                be.PlannedExecution(
                    execution.id,
                    None
                    if execution.cell_id == SCRATCH_CELL_ID
                    else execution.cell_id,
                    code_hash(code),
                    code if execution.cell_id == SCRATCH_CELL_ID else None,
                    caused_by=parent.id if parent is not None else None,
                ),
            ),
        )

    def _conclude(
        self,
        execution: _Execution,
        *,
        error: protocol.Error | None = None,
        interrupted: bool = False,
    ) -> list[be.Message]:
        if execution.ended:
            return []
        previous = execution.outcome
        exceptions = [
            e
            for e in execution.errors
            if not isinstance(e, MarimoInterruptionError)
        ]
        if error is not None:
            execution.outcome = protocol.ErrorOutcome(error)
        elif exceptions:
            execution.outcome = protocol.ErrorOutcome(_describe(exceptions[0]))
        elif interrupted or execution.errors:
            execution.outcome = protocol.InterruptedOutcome()
        execution.ended = True
        out: list[be.Message] = []
        if not execution.reported or execution.outcome != previous:
            out.append(be.Concluded(execution.id, execution.outcome))
        out.append(be.Status(execution.id, "completed"))
        self._failed |= isinstance(execution.outcome, protocol.ErrorOutcome)
        self.interrupted |= isinstance(
            execution.outcome, protocol.InterruptedOutcome
        )
        # The core keeps the reported outcome; release the payload here
        # while the translator stays alive for late output.
        execution.outcome = protocol.ValueOutcome(None)
        execution.errors.clear()
        return out

    def finish(
        self, *, error: protocol.Error | None = None
    ) -> list[be.Message]:
        """Close the cycle after the kernel's completion boundary."""
        if self._finished:
            return []
        self._finished = True
        error = error or self._error
        out: list[be.Message] = []
        if self._code is not None and not self._executions:
            out.append(
                self._plan(
                    ExecutionNotification(
                        execution_id="unsubmitted",
                        cell_id=SCRATCH_CELL_ID,
                        run_id=self.run_id,
                        phase="planned",
                        code=self._code,
                    )
                )
            )
        for execution in self._executions.values():
            out.extend(
                self._conclude(
                    execution, error=error, interrupted=self.interrupted
                )
            )
        self._code = None
        self._error = None
        outcome: protocol.RunOutcome = "succeeded"
        if error is not None or self._failed:
            outcome = "failed"
        if self.interrupted:
            outcome = "interrupted"
        out.append(be.Done(self.run_id, outcome))
        return out

    def _console(
        self, execution: _Execution, notification: CellNotification
    ) -> list[be.Message]:
        if notification.console is None:
            return []
        entries = (
            notification.console
            if isinstance(notification.console, list)
            else [notification.console]
        )
        out: list[be.Message] = []
        for entry in entries:
            if entry is None or entry.channel not in (
                CellChannel.STDOUT,
                CellChannel.STDERR,
            ):
                continue
            out.append(
                be.Produced(
                    protocol.Console(
                        id=protocol.ItemId(f"{execution.id}-{execution.seq}"),
                        execution_id=execution.id,
                        seq=execution.seq,
                        name="stdout"
                        if entry.channel == CellChannel.STDOUT
                        else "stderr",
                        text=_plain(str(entry.data)),
                    )
                )
            )
            execution.seq += 1
        return out


def _plain(text: str) -> str:
    """Remove marimo's HTML syntax highlighting from console text."""
    if not is_code_highlighting(text):
        return text
    return html.unescape(re.sub(r"<[^>]+>", "", text))


def _describe(error: Error) -> protocol.Error:
    """Convert a kernel error to a host protocol error."""
    if isinstance(error, MarimoExceptionRaisedError):
        traceback = None
        if error.traceback:
            traceback = protocol.DisplayData(
                mimetype="text/html"
                if is_code_highlighting(error.traceback)
                else "text/plain",
                data=error.traceback,
            )
        return protocol.Error(
            kind="exception",
            name=error.exception_type,
            message=error.msg,
            traceback=traceback,
            source="marimo",
            severity="error",
            range=None,
            related=(),
        )
    if isinstance(error, MarimoSyntaxError):
        return protocol.Error(
            kind="syntax",
            name=None,
            message=error.msg,
            traceback=None,
            source="marimo",
            severity="error",
            range=None,
            related=(),
        )
    if isinstance(error, UnknownError):
        return protocol.Error(
            kind="internal",
            name=error.error_type,
            message=error.msg,
            traceback=None,
            source="marimo",
            severity="error",
            range=None,
            related=(),
        )
    return protocol.Error(
        kind="internal",
        name=None,
        message=error.describe(),
        traceback=None,
        source="marimo",
        severity="error",
        range=None,
        related=(),
    )
