# Copyright 2026 Marimo. All rights reserved.
"""Kernel notifications translated into runs and their member executions."""

from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from marimo._core import backend as be, protocol
from marimo._core.code import code_fingerprint
from marimo._messaging.cell_output import CellChannel
from marimo._messaging.errors import (
    ANCESTOR_RAISED,
    CycleError,
    Error,
    ImportStarError,
    LazyImportError,
    MarimoAncestorPreventedError,
    MarimoAncestorStoppedError,
    MarimoExceptionRaisedError,
    MarimoInternalError,
    MarimoInterruptionError,
    MarimoSQLError,
    MarimoStrictExecutionError,
    MarimoSyntaxError,
    MultipleDefinitionError,
    SetupRootError,
    UnknownError,
)
from marimo._messaging.notification import (
    CellNotification,
    CompletedRunNotification,
    ExecutionNotification,
    InterruptedNotification,
    NotificationMessage,
    VariableValuesNotification,
)
from marimo._messaging.tracebacks import is_code_highlighting
from marimo._runtime.scratch import SCRATCH_CELL_ID
from marimo._server.host import diagnostics

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Sequence

    CellOrder = Callable[[], Sequence[str]]
    """The document's cell ids in order, read when an error names cells."""


def _unordered() -> Sequence[str]:
    return ()


@dataclass
class _Execution:
    id: protocol.ExecutionId
    cell_id: str
    ended: bool = False
    outcome: protocol.Outcome = field(
        default_factory=lambda: protocol.ValueOutcome(None)
    )
    errors: list[Error] = field(default_factory=list)
    seq: int = 0
    code: str | None = None


class RunTranslator:
    """Track evaluations within one bounded reactive cycle."""

    def __init__(
        self,
        run_id: protocol.RunId,
        code: str | None,
        cell_order: CellOrder = _unordered,
    ) -> None:
        self.run_id = run_id
        self._code = code
        self._cell_order = cell_order
        self._finished = False
        self.completed = False
        self.interrupted = False
        self._failed = False
        self._error: protocol.Error | None = None
        self._executions: dict[str, _Execution] = {}

    @property
    def started(self) -> bool:
        """Whether the kernel has planned an execution for this run."""
        return bool(self._executions)

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
                return [be.Started(execution.id)]
            return self._conclude(
                execution,
                depends_on=notification.depends_on,
                skipped=notification.skipped,
            )

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
                out.append(be.Concluded(execution.id, execution.outcome))
        return out

    def _plan(self, notification: ExecutionNotification) -> be.Planned:
        code = notification.code
        execution = _Execution(
            protocol.ExecutionId(notification.execution_id),
            notification.cell_id,
            code=code,
        )
        self._executions[notification.execution_id] = execution
        parent = self._executions.get(notification.caused_by or "")
        assert notification.code_fingerprint is not None
        return be.Planned(
            self.run_id,
            (
                be.PlannedExecution(
                    execution.id,
                    None
                    if execution.cell_id == SCRATCH_CELL_ID
                    else execution.cell_id,
                    notification.code_fingerprint,
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
        depends_on: dict[str, protocol.Revision | None] | None = None,
        skipped: str | None = None,
    ) -> list[be.Message]:
        if execution.ended:
            return []
        skips = [e for e in execution.errors if _skip_reason(e) is not None]
        exceptions = [
            e
            for e in execution.errors
            if not isinstance(e, MarimoInterruptionError) and e not in skips
        ]
        if error is not None:
            execution.outcome = protocol.ErrorOutcome(error)
        elif skipped is not None:
            execution.outcome = _declined(skipped, execution.cell_id)
        elif exceptions:
            execution.outcome = protocol.ErrorOutcome(
                _describe(
                    exceptions[0],
                    cell_id=None
                    if execution.cell_id == SCRATCH_CELL_ID
                    else execution.cell_id,
                    code=execution.code,
                    cell_order=self._cell_order,
                )
            )
        elif skips:
            execution.outcome = _skipped(skips[0], execution.cell_id)
        elif interrupted or execution.errors:
            execution.outcome = protocol.InterruptedOutcome()
        execution.ended = True
        out: list[be.Message] = [
            be.Completed(execution.id, execution.outcome, depends_on or {})
        ]
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
                        execution_id=f"{self.run_id}-unsubmitted",
                        cell_id=SCRATCH_CELL_ID,
                        run_id=self.run_id,
                        phase="planned",
                        code=self._code,
                        code_fingerprint=code_fingerprint(self._code),
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
            if entry is not None and entry.channel == CellChannel.STDIN:
                if (
                    not execution.ended
                    and not self._finished
                    and isinstance(entry.input_id, str)
                ):
                    out.append(
                        be.Produced(
                            protocol.Input(
                                id=protocol.ItemId(entry.input_id),
                                execution_id=execution.id,
                                seq=execution.seq,
                                prompt=str(entry.data),
                                password=entry.mimetype == "text/password",
                                status="pending",
                            )
                        )
                    )
                    execution.seq += 1
                continue
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


class RunTranslators:
    """The translators for a kernel's runs, by run id.

    A host submits some runs itself. The kernel schedules others, such as
    a UI interaction's reactive work or a legacy client's request, and
    those get a translator when their first execution is planned.
    """

    def __init__(self, cell_order: CellOrder = _unordered) -> None:
        self._cell_order = cell_order
        self._translators: dict[str, RunTranslator] = {}

    def __iter__(self) -> Iterator[str]:
        return iter(self._translators)

    def __len__(self) -> int:
        return len(self._translators)

    def add(self, translator: RunTranslator) -> None:
        self._translators[translator.run_id] = translator

    def get(self, run_id: str) -> RunTranslator | None:
        return self._translators.get(run_id)

    def forget(self, run_id: str) -> None:
        self._translators.pop(run_id, None)

    def clear(self) -> None:
        self._translators.clear()

    def feed(
        self, notification: NotificationMessage
    ) -> tuple[RunTranslator | None, list[be.Message]]:
        """Translate a notification about a run, if it concerns one."""
        if not isinstance(
            notification,
            (
                CellNotification,
                ExecutionNotification,
                CompletedRunNotification,
                InterruptedNotification,
            ),
        ):
            return None, []
        run_id = notification.run_id
        if run_id is None:
            return None, []
        out: list[be.Message] = []
        translator = self._translators.get(run_id)
        if translator is None:
            if (
                not isinstance(notification, ExecutionNotification)
                or notification.phase != "planned"
            ):
                return None, []
            translator = RunTranslator(
                protocol.RunId(run_id),
                notification.code
                if notification.cell_id == SCRATCH_CELL_ID
                else None,
                self._cell_order,
            )
            self.add(translator)
            out.append(be.Scheduled(translator.run_id))
        out.extend(translator.feed(notification))
        return translator, out


def variable_messages(notification: NotificationMessage) -> list[be.Message]:
    """Report the variables a notification binds or unbinds."""
    if not isinstance(notification, VariableValuesNotification):
        return []
    out: list[be.Message] = [
        be.Unbound(protocol.ExecutionId(removed.execution_id), removed.name)
        for removed in notification.removed
    ]
    for value in notification.variables:
        if value.execution_id is None or value.revision is None:
            continue
        out.append(
            be.Produced(
                protocol.Variable(
                    execution_id=protocol.ExecutionId(value.execution_id),
                    id=protocol.ItemId(
                        f"{value.execution_id}-variable-{value.name}"
                    ),
                    name=value.name,
                    preview=value.value,
                    revision=value.revision,
                    type=value.datatype,
                )
            )
        )
    return out


def _plain(text: str) -> str:
    """Remove marimo's HTML syntax highlighting from console text."""
    if not is_code_highlighting(text):
        return text
    return html.unescape(re.sub(r"<[^>]+>", "", text))


def _skip_reason(error: Error) -> str | None:
    """The reason a kernel error means the cell did not evaluate, if it does."""
    if isinstance(error, MarimoAncestorStoppedError):
        return "upstream-stopped"
    if isinstance(error, MarimoAncestorPreventedError):
        return "upstream-failed"
    if (
        isinstance(error, MarimoExceptionRaisedError)
        # A NameError blamed on another cell names that cell too, so the
        # exception type is what tells a cancelled cell from one that ran.
        and error.exception_type == ANCESTOR_RAISED
    ):
        return "upstream-failed"
    return None


def _declined(reason: str, cell_id: str) -> protocol.SkippedOutcome:
    """Describe an attempt the kernel ended without evaluating it."""
    message = (
        "Replaced by a newer execution of this cell before it started"
        if reason == "superseded"
        else "Did not run"
    )
    return protocol.SkippedOutcome(
        reason=reason,
        message=message,
        related=(
            protocol.Related(
                cell_id=protocol.CellId(cell_id),
                range=None,
                message="Changed while queued",
            ),
        ),
    )


def _skipped(error: Error, cell_id: str) -> protocol.SkippedOutcome:
    """Describe a cell that did not evaluate because of the cells it names.

    The kernel's message ends where the editor appends a link to the cause,
    so the trailing colon goes and the cause is named in `related`.
    """
    reason = _skip_reason(error)
    assert reason is not None
    involved: list[tuple[str, str]] = []
    if isinstance(error, MarimoAncestorStoppedError):
        involved.append((error.raising_cell, "Stopped with `mo.stop`"))
    elif isinstance(error, MarimoAncestorPreventedError):
        involved.append((error.raising_cell, "Could not resolve a reference"))
        if error.blamed_cell is not None:
            involved.append((error.blamed_cell, "Expected to define it"))
    elif isinstance(error, MarimoExceptionRaisedError):
        assert error.raising_cell is not None
        involved.append((error.raising_cell, "Raised an exception"))
    involved = [(cell, part) for cell, part in involved if cell != cell_id]
    involved.append((cell_id, "Did not run"))
    return protocol.SkippedOutcome(
        reason=reason,
        message=error.describe().rstrip(": "),
        related=tuple(
            protocol.Related(
                cell_id=protocol.CellId(involved_cell),
                range=None,
                message=part,
            )
            for involved_cell, part in involved
        ),
    )


def _point(
    line: int | None, byte_column: int = 0, code: str | None = None
) -> protocol.Range | None:
    """A range at one position, from the kernel's one-based line and AST column."""
    if line is None or line < 1:
        return None
    character = byte_column
    if code is not None:
        character = diagnostics.utf16_from_utf8(code, line - 1, byte_column)
    position = protocol.Position(line=line - 1, character=character)
    return protocol.Range(start=position, end=position)


def _describe(
    error: Error,
    *,
    cell_id: str | None = None,
    code: str | None = None,
    cell_order: CellOrder = _unordered,
) -> protocol.Error:
    """Convert a kernel error to a host protocol error.

    Each kernel error keeps its own kind, so a client can tell them apart,
    and names the cells involved in `related`, so it can link to them.
    """
    if isinstance(error, MarimoExceptionRaisedError):
        traceback = None
        if error.traceback:
            traceback = protocol.DisplayData(
                mimetype="text/html"
                if is_code_highlighting(error.traceback)
                else "text/plain",
                data=error.traceback,
            )
        related: tuple[protocol.Related, ...] = ()
        if error.raising_cell is not None:
            related = (
                protocol.Related(
                    cell_id=protocol.CellId(error.raising_cell),
                    range=None,
                    message="Raised it",
                ),
            )
        return diagnostics.error(
            "exception",
            error.msg,
            name=error.exception_type,
            traceback=traceback,
            related=related,
        )
    if isinstance(error, MarimoSyntaxError):
        return diagnostics.error(
            "invalid-syntax", error.msg, range_=_point(error.lineno)
        )
    if isinstance(error, CycleError):
        return diagnostics.cycle(error)
    if isinstance(error, SetupRootError):
        return diagnostics.error(
            "setup-refs",
            error.describe(),
            related=diagnostics.depends_on(error.edges_with_vars),
        )
    if isinstance(error, MultipleDefinitionError):
        definers: set[str] = set(error.cells)
        if cell_id is not None:
            definers.add(cell_id)
        return diagnostics.multiple_definitions(
            None if cell_id is None else protocol.CellId(cell_id),
            error.name,
            [
                protocol.CellId(definer)
                for definer in sorted(
                    definers, key=diagnostics.by_position(cell_order())
                )
            ],
        )
    if isinstance(error, ImportStarError):
        return diagnostics.error(
            "import-star", error.msg, range_=_point(error.lineno)
        )
    if isinstance(error, LazyImportError):
        return diagnostics.error(
            "lazy-import", error.msg, range_=_point(error.lineno)
        )
    if isinstance(error, MarimoStrictExecutionError):
        blamed: tuple[protocol.Related, ...] = ()
        if error.blamed_cell is not None:
            blamed = (
                protocol.Related(
                    cell_id=protocol.CellId(error.blamed_cell),
                    range=None,
                    message=f"Defines {error.ref}",
                ),
            )
        return diagnostics.error("strict-exception", error.msg, related=blamed)
    if isinstance(error, MarimoSQLError):
        message = (
            error.msg if error.hint is None else f"{error.msg}\n{error.hint}"
        )
        return diagnostics.error(
            "sql",
            message,
            range_=_point(error.node_lineno, error.node_col_offset, code),
        )
    if isinstance(error, MarimoInternalError):
        return diagnostics.error("internal", error.msg, name=error.error_id)
    if isinstance(error, UnknownError):
        return diagnostics.error("internal", error.msg, name=error.error_type)
    return diagnostics.error("internal", error.describe())
