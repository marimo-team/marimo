# Copyright 2026 Marimo. All rights reserved.
"""Translation of kernel notifications into backend messages."""

from __future__ import annotations

import pytest
from dirty_equals import IsStr
from inline_snapshot import snapshot

from marimo._core.backend import (
    Concluded,
    Done,
    Planned,
    PlannedExecution,
    Produced,
    Status,
)
from marimo._core.document import code_hash
from marimo._core.protocol import (
    Console,
    DisplayData,
    Error,
    ErrorOutcome,
    ExecutionId,
    InterruptedOutcome,
    RunId,
    ValueOutcome,
)
from marimo._messaging.cell_output import CellChannel, CellOutput
from marimo._messaging.errors import (
    MarimoExceptionRaisedError,
    MarimoInterruptionError,
)
from marimo._messaging.notification import (
    CellNotification,
    CompletedRunNotification,
    ExecutionNotification,
)
from marimo._runtime.scratch import SCRATCH_CELL_ID
from marimo._server.host.translate import RunTranslator
from marimo._types.ids import CellId_t


def scratch(**fields: object) -> CellNotification:
    return CellNotification(
        cell_id=SCRATCH_CELL_ID, run_id="r1", execution_id="scratch", **fields
    )  # type: ignore[arg-type]


def attempt(phase: str, **fields: object) -> ExecutionNotification:
    return ExecutionNotification(
        cell_id=SCRATCH_CELL_ID,
        run_id="r1",
        execution_id="scratch",
        phase=phase,
        code="3 * 3" if phase == "planned" else None,
        **fields,
    )  # type: ignore[arg-type]


def test_a_run_that_prints_and_shows_a_value() -> None:
    t = RunTranslator(RunId("r1"), "3 * 3")

    messages = t.feed(attempt("planned"))
    messages.extend(t.feed(attempt("running")))
    messages.extend(t.feed(scratch(console=CellOutput.stdout("2\n"))))
    messages.extend(
        t.feed(
            scratch(
                output=CellOutput(
                    channel=CellChannel.OUTPUT,
                    mimetype="text/html",
                    data="<pre>9</pre>",
                )  # type: ignore[arg-type]
            )
        )
    )
    assert t.feed(CompletedRunNotification(run_id="other")) == []
    assert not t.completed
    messages.extend(t.feed(attempt("completed")))
    messages.extend(t.feed(CompletedRunNotification(run_id="r1")))
    assert t.completed
    messages.extend(t.finish())

    assert messages == snapshot(
        [
            Planned(
                run_id=RunId("r1"),
                executions=(
                    PlannedExecution(
                        id=ExecutionId("r1-1"),
                        cell_id=None,
                        code_hash=code_hash("3 * 3"),
                        code="3 * 3",
                        caused_by=None,
                    ),
                ),
            ),
            Status(execution_id=ExecutionId("r1-1"), status="running"),
            Produced(
                item=Console(
                    execution_id=ExecutionId("r1-1"),
                    id=IsStr(),
                    name="stdout",
                    seq=0,
                    text="2\n",
                )
            ),
            Concluded(
                execution_id=ExecutionId("r1-1"),
                outcome=ValueOutcome(
                    display=DisplayData(
                        data="<pre>9</pre>", mimetype="text/html"
                    )
                ),
            ),
            Status(execution_id=ExecutionId("r1-1"), status="completed"),
            Done(run_id=RunId("r1"), outcome="succeeded"),
        ]
    )


def test_unrelated_output_does_not_belong_to_the_scratch_execution() -> None:
    t = RunTranslator(RunId("r1"), "3 * 3")
    other = CellNotification(
        cell_id=CellId_t("c1"), console=CellOutput.stdout("x")
    )
    assert t.feed(other) == []
    t.feed(attempt("planned"))
    t.feed(attempt("running"))
    assert t.feed(other) == []
    assert (
        t.feed(
            CellNotification(
                cell_id=SCRATCH_CELL_ID,
                run_id="other",
                console=CellOutput.stdout("x"),
            )
        )
        == []
    )


def test_an_exception_ends_the_run_in_error() -> None:
    t = RunTranslator(RunId("r1"), "3 * 3")
    t.feed(attempt("planned"))
    t.feed(attempt("running"))
    error = MarimoExceptionRaisedError(
        msg="division by zero",
        exception_type="ZeroDivisionError",
        raising_cell=None,
        traceback="Traceback...\nZeroDivisionError: division by zero\n",
    )
    assert t.feed(scratch(output=CellOutput.errors([error]))) == []

    assert t.finish() == snapshot(
        [
            Concluded(
                execution_id=ExecutionId("r1-1"),
                outcome=ErrorOutcome(
                    error=Error(
                        source="marimo",
                        severity="error",
                        range=None,
                        related=(),
                        kind="exception",
                        message="division by zero",
                        name="ZeroDivisionError",
                        traceback=DisplayData(
                            data="""\
Traceback...
ZeroDivisionError: division by zero
""",
                            mimetype="text/plain",
                        ),
                    )
                ),
            ),
            Status(execution_id=ExecutionId("r1-1"), status="completed"),
            Done(run_id=RunId("r1"), outcome="failed"),
        ]
    )


@pytest.mark.parametrize("interrupted_by", ["kernel", "client"])
def test_an_interruption_ends_the_run_interrupted(
    interrupted_by: str,
) -> None:
    t = RunTranslator(RunId("r1"), "3 * 3")
    t.feed(attempt("planned"))
    t.feed(attempt("running"))
    if interrupted_by == "kernel":
        t.feed(scratch(output=CellOutput.errors([MarimoInterruptionError()])))
    else:
        t.interrupted = True

    assert t.finish() == snapshot(
        [
            Concluded(
                execution_id=ExecutionId("r1-1"),
                outcome=InterruptedOutcome(),
            ),
            Status(execution_id=ExecutionId("r1-1"), status="completed"),
            Done(run_id=RunId("r1"), outcome="interrupted"),
        ]
    )


def test_console_items_number_in_order_and_lose_highlighting() -> None:
    t = RunTranslator(RunId("r1"), "3 * 3")
    t.feed(attempt("planned"))
    t.feed(attempt("running"))
    out = t.feed(
        scratch(
            console=[
                CellOutput.stdout("a"),
                CellOutput.stderr('<span class="codehilite">&lt;b&gt;</span>'),
            ]
        )
    )
    items = [m.item for m in out if isinstance(m, Produced)]
    assert len({i.id for i in items}) == 2
    assert out == snapshot(
        [
            Produced(
                item=Console(
                    execution_id=ExecutionId("r1-1"),
                    id=IsStr(),
                    name="stdout",
                    seq=0,
                    text="a",
                )
            ),
            Produced(
                item=Console(
                    execution_id=ExecutionId("r1-1"),
                    id=IsStr(),
                    name="stderr",
                    seq=1,
                    text="<b>",
                )
            ),
        ]
    )


def test_late_output_keeps_its_evaluation_when_a_cell_runs_again() -> None:
    translator = RunTranslator(RunId("r1"), None)
    ids = []
    for identity in ("first", "second"):
        planned = translator.feed(
            ExecutionNotification(
                cell_id=CellId_t("cell"),
                run_id="r1",
                phase="planned",
                execution_id=identity,
                code="pass",
            )
        )[0]
        assert isinstance(planned, Planned)
        ids.append(planned.executions[0].id)
        translator.feed(
            ExecutionNotification(
                cell_id=CellId_t("cell"),
                run_id="r1",
                phase="completed",
                execution_id=identity,
            )
        )
    assert ids[0] != ids[1]
    assert translator.finish() == [Done(RunId("r1"), "succeeded")]
    [output] = translator.feed(
        CellNotification(
            cell_id=CellId_t("cell"),
            run_id="r1",
            execution_id="first",
            console=CellOutput.stdout("late"),
        )
    )
    assert isinstance(output, Produced)
    assert output.item.execution_id == ids[0]


@pytest.mark.parametrize(
    ("error", "outcome_type", "run_outcome"),
    [
        (MarimoInterruptionError(), InterruptedOutcome, "interrupted"),
        (
            MarimoExceptionRaisedError(
                "ancestor failed", "RuntimeError", None
            ),
            ErrorOutcome,
            "failed",
        ),
    ],
)
def test_skipped_cells_report_their_error_after_becoming_idle(
    error: object, outcome_type: type, run_outcome: str
) -> None:
    translator = RunTranslator(RunId("r1"), None)

    def cell(**fields: object) -> CellNotification:
        return CellNotification(
            cell_id=CellId_t("cell"),
            run_id="r1",
            execution_id="skipped",
            **fields,
        )  # type: ignore[arg-type]

    translator.feed(
        ExecutionNotification(
            cell_id=CellId_t("cell"),
            run_id="r1",
            execution_id="skipped",
            phase="planned",
            code="pass",
        )
    )
    assert translator.feed(cell(status="idle")) == []
    translator.feed(cell(output=CellOutput.errors([error])))  # type: ignore[list-item]
    messages = translator.feed(
        ExecutionNotification(
            cell_id=CellId_t("cell"),
            run_id="r1",
            execution_id="skipped",
            phase="completed",
        )
    )
    messages.extend(translator.finish())
    assert isinstance(messages[0], Concluded)
    assert isinstance(messages[0].outcome, outcome_type)
    assert messages[1] == Status(ExecutionId("r1-1"), "completed")
    assert messages[2] == Done(RunId("r1"), run_outcome)  # type: ignore[arg-type]
