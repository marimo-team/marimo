# Copyright 2026 Marimo. All rights reserved.
"""Translation of kernel notifications into backend messages."""

from __future__ import annotations

import msgspec
import pytest
from dirty_equals import IsStr
from inline_snapshot import snapshot

from marimo._core import backend as be, protocol
from marimo._core.backend import (
    Completed,
    Concluded,
    Done,
    Planned,
    PlannedExecution,
    Produced,
    Started,
)
from marimo._core.code import code_fingerprint
from marimo._core.document import Document, DocumentCell
from marimo._core.protocol import (
    CellId,
    Console,
    DisplayData,
    Error,
    ErrorOutcome,
    ExecutionId,
    InterruptedOutcome,
    Position,
    Range,
    Related,
    Revision,
    RunId,
    SkippedOutcome,
    ValueOutcome,
)
from marimo._messaging.cell_output import CellChannel, CellOutput
from marimo._messaging.errors import (
    CycleError,
    ImportStarError,
    LazyImportError,
    MarimoAncestorPreventedError,
    MarimoAncestorStoppedError,
    MarimoExceptionRaisedError,
    MarimoInternalError,
    MarimoInterruptionError,
    MarimoSQLError,
    MarimoStrictExecutionError,
    MultipleDefinitionError,
    SetupRootError,
)
from marimo._messaging.notification import (
    CellNotification,
    CompletedRunNotification,
    ExecutionNotification,
)
from marimo._runtime.scratch import SCRATCH_CELL_ID
from marimo._server.host.analysis import CellAnalyzer
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
        code_fingerprint=code_fingerprint("3 * 3")
        if phase == "planned"
        else None,
        **fields,
    )  # type: ignore[arg-type]


def test_a_superseded_attempt_is_skipped_and_its_run_succeeds() -> None:
    t = RunTranslator(RunId("r1"), None)
    planned = ExecutionNotification(
        cell_id=CellId_t("b"),
        run_id="r1",
        execution_id="b1",
        phase="planned",
        code="print(x)",
        code_fingerprint=code_fingerprint("print(x)"),
    )
    superseded = ExecutionNotification(
        cell_id=CellId_t("b"),
        run_id="r1",
        execution_id="b1",
        phase="completed",
        skipped="superseded",
    )
    messages = t.feed(planned)
    messages.extend(t.feed(superseded))
    messages.extend(t.feed(CompletedRunNotification(run_id="r1")))
    messages.extend(t.finish())

    completed = next(m for m in messages if isinstance(m, be.Completed))
    assert completed.outcome == protocol.SkippedOutcome(
        reason="superseded",
        message="Replaced by a newer execution of this cell before it started",
        related=(
            protocol.Related(
                cell_id=protocol.CellId("b"),
                range=None,
                message="Changed while queued",
            ),
        ),
    )
    assert messages[-1] == be.Done(RunId("r1"), "succeeded")


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
    inputs = {"x": Revision(ExecutionId("producer"), 2), "print": None}
    messages.extend(t.feed(attempt("completed", depends_on=inputs)))
    messages.extend(t.feed(CompletedRunNotification(run_id="r1")))
    assert t.completed
    messages.extend(t.finish())

    assert messages == snapshot(
        [
            Planned(
                run_id=RunId("r1"),
                executions=(
                    PlannedExecution(
                        id=ExecutionId("scratch"),
                        cell_id=None,
                        code_fingerprint=code_fingerprint("3 * 3"),
                        code="3 * 3",
                        caused_by=None,
                    ),
                ),
            ),
            Started(execution_id=ExecutionId("scratch")),
            Produced(
                item=Console(
                    execution_id=ExecutionId("scratch"),
                    id=IsStr(),
                    name="stdout",
                    seq=0,
                    text="2\n",
                )
            ),
            Concluded(
                execution_id=ExecutionId("scratch"),
                outcome=ValueOutcome(
                    display=DisplayData(
                        data="<pre>9</pre>", mimetype="text/html"
                    )
                ),
            ),
            Completed(
                execution_id=ExecutionId("scratch"),
                outcome=ValueOutcome(
                    DisplayData(data="<pre>9</pre>", mimetype="text/html")
                ),
                depends_on=inputs,
            ),
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
            Completed(
                execution_id=ExecutionId("scratch"),
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
            Completed(
                execution_id=ExecutionId("scratch"),
                outcome=InterruptedOutcome(),
            ),
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
                    execution_id=ExecutionId("scratch"),
                    id=IsStr(),
                    name="stdout",
                    seq=0,
                    text="a",
                )
            ),
            Produced(
                item=Console(
                    execution_id=ExecutionId("scratch"),
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
                code_fingerprint=code_fingerprint("pass"),
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
    assert ids == ["first", "second"]
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


def test_unsubmitted_runs_have_distinct_executions() -> None:
    executions = []
    for run_id in ("r1", "r2"):
        translator = RunTranslator(RunId(run_id), "print('never ran')")
        translator.interrupted = True
        planned, completed, done = translator.finish()
        assert isinstance(planned, Planned)
        [execution] = planned.executions
        executions.append(execution.id)
        assert (completed, done) == (
            Completed(execution.id, InterruptedOutcome()),
            Done(RunId(run_id), "interrupted"),
        )
    assert len(set(executions)) == 2


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
        (
            MarimoExceptionRaisedError(
                "An ancestor raised an exception (RuntimeError): ",
                "Ancestor raised",
                CellId_t("a"),
            ),
            SkippedOutcome,
            "succeeded",
        ),
        (
            MarimoExceptionRaisedError(
                "Name `x` is not defined. It was expected to be defined in ",
                "NameError",
                CellId_t("a"),
            ),
            ErrorOutcome,
            "failed",
        ),
        (
            MarimoAncestorStoppedError(
                "This cell wasn't run because an ancestor was stopped with `mo.stop`: ",
                CellId_t("a"),
            ),
            SkippedOutcome,
            "succeeded",
        ),
        (
            MarimoAncestorPreventedError(
                "This cell wasn't run because an ancestor failed to resolve the reference `x` : ",
                CellId_t("a"),
                CellId_t("b"),
            ),
            SkippedOutcome,
            "succeeded",
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
            code_fingerprint=code_fingerprint("pass"),
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
    assert isinstance(messages[0], Completed)
    assert isinstance(messages[0].outcome, outcome_type)
    assert messages[1] == Done(RunId("r1"), run_outcome)  # type: ignore[arg-type]


@pytest.mark.parametrize("code", ["x = 1", None])
def test_planned_fingerprint_is_preserved_without_rehashing(
    code: str | None,
) -> None:
    translator = RunTranslator(RunId("r1"), None)
    assert translator.feed(
        ExecutionNotification(
            cell_id=CellId_t("a"),
            run_id="r1",
            execution_id="execution",
            phase="planned",
            code=code,
            code_fingerprint="custom:v1:a",
        )
    ) == [
        Planned(
            RunId("r1"),
            (
                PlannedExecution(
                    ExecutionId("execution"), "a", "custom:v1:a", None
                ),
            ),
        )
    ]


@pytest.mark.parametrize(
    ("error", "reason", "related"),
    [
        (
            MarimoAncestorStoppedError(
                msg="This cell wasn't run because an ancestor was stopped with `mo.stop`: ",
                raising_cell=CellId_t("a"),
            ),
            "upstream-stopped",
            [("a", "Stopped with `mo.stop`"), ("c", "Did not run")],
        ),
        (
            MarimoExceptionRaisedError(
                msg="An ancestor raised an exception (RuntimeError): ",
                exception_type="Ancestor raised",
                raising_cell=CellId_t("a"),
            ),
            "upstream-failed",
            [("a", "Raised an exception"), ("c", "Did not run")],
        ),
        (
            MarimoAncestorPreventedError(
                msg="This cell wasn't run because an ancestor failed to resolve the reference `x` : ",
                raising_cell=CellId_t("a"),
                blamed_cell=CellId_t("b"),
            ),
            "upstream-failed",
            [
                ("a", "Could not resolve a reference"),
                ("b", "Expected to define it"),
                ("c", "Did not run"),
            ],
        ),
    ],
)
def test_a_skipped_cell_names_its_reason_and_the_cells_involved(
    error: object, reason: str, related: list[tuple[str, str]]
) -> None:
    translator = RunTranslator(RunId("r1"), None)
    translator.feed(
        ExecutionNotification(
            cell_id=CellId_t("c"),
            run_id="r1",
            execution_id="skipped",
            phase="planned",
            code="x",
            code_fingerprint=code_fingerprint("x"),
        )
    )
    translator.feed(
        CellNotification(
            cell_id=CellId_t("c"),
            run_id="r1",
            execution_id="skipped",
            output=CellOutput.errors([error]),  # type: ignore[list-item]
        )
    )
    [completed] = translator.feed(
        ExecutionNotification(
            cell_id=CellId_t("c"),
            run_id="r1",
            execution_id="skipped",
            phase="completed",
        )
    )
    assert isinstance(completed, Completed)
    outcome = completed.outcome
    assert isinstance(outcome, SkippedOutcome)
    assert outcome.reason == reason
    assert outcome.message.startswith(("This cell wasn't run", "An ancestor"))
    assert not outcome.message.endswith((":", " "))
    assert [(r.cell_id, r.message) for r in outcome.related] == related
    assert translator.finish() == [Done(RunId("r1"), "succeeded")]


def planned(cell_id: str, code: str) -> ExecutionNotification:
    return ExecutionNotification(
        cell_id=CellId_t(cell_id),
        run_id="r1",
        execution_id=f"{cell_id}1",
        phase="planned",
        code=code,
        code_fingerprint=code_fingerprint(code),
    )


def running(cell_id: str) -> ExecutionNotification:
    return ExecutionNotification(
        cell_id=CellId_t(cell_id),
        run_id="r1",
        execution_id=f"{cell_id}1",
        phase="running",
    )


def cell_output(cell_id: str, output: CellOutput) -> CellNotification:
    return CellNotification(
        cell_id=CellId_t(cell_id),
        run_id="r1",
        execution_id=f"{cell_id}1",
        output=output,
    )


def _point(line: int, character: int = 0) -> Range:
    position = Position(line=line, character=character)
    return Range(start=position, end=position)


@pytest.mark.parametrize(
    ("error", "kind", "related", "range_"),
    [
        (
            MarimoExceptionRaisedError(
                msg="boom", exception_type="ValueError", raising_cell="a"
            ),
            "exception",
            (Related(cell_id=CellId("a"), range=None, message="Raised it"),),
            None,
        ),
        (
            LazyImportError(msg="lazy import of foo", lineno=5),
            "lazy-import",
            (),
            _point(4),
        ),
        (
            CycleError(
                edges_with_vars=(("a", ("x",), "b"), ("b", ("y", "z"), "a"))
            ),
            "cycle-dependencies",
            (
                Related(
                    cell_id=CellId("a"),
                    range=None,
                    message="Depends on b through y, z",
                ),
                Related(
                    cell_id=CellId("b"),
                    range=None,
                    message="Depends on a through x",
                ),
            ),
            None,
        ),
        (
            SetupRootError(edges_with_vars=(("setup", ("x",), "c"),)),
            "setup-refs",
            (
                Related(
                    cell_id=CellId("c"),
                    range=None,
                    message="Depends on setup through x",
                ),
            ),
            None,
        ),
        (
            MultipleDefinitionError(name="x", cells=("b", "a")),
            "multiple-definitions",
            (
                Related(cell_id=CellId("a"), range=None, message="Defines x"),
                Related(cell_id=CellId("b"), range=None, message="Defines x"),
                Related(cell_id=CellId("c"), range=None, message="Defines x"),
            ),
            None,
        ),
        (
            ImportStarError(msg="import * is not allowed", lineno=3),
            "import-star",
            (),
            _point(2),
        ),
        (
            MarimoStrictExecutionError(
                msg="x is not defined", ref="x", blamed_cell="a"
            ),
            "strict-exception",
            (Related(cell_id=CellId("a"), range=None, message="Defines x"),),
            None,
        ),
        (
            MarimoSQLError(
                msg="no such table",
                sql_statement="select * from t",
                node_lineno=2,
                node_col_offset=4,
            ),
            "sql",
            (),
            _point(1, 4),
        ),
    ],
)
def test_each_kernel_error_keeps_its_kind_and_names_the_cells_involved(
    error: object,
    kind: str,
    related: tuple[Related, ...],
    range_: Range | None,
) -> None:
    t = RunTranslator(RunId("r1"), None)
    t.feed(planned("c", "x = 1\nmo.sql('select * from t')"))
    t.feed(running("c"))
    t.feed(cell_output("c", CellOutput.errors([error])))  # type: ignore[list-item]

    completed = t.finish()[0]
    assert isinstance(completed, Completed)
    assert isinstance(completed.outcome, ErrorOutcome)
    described = completed.outcome.error
    assert described.source == "marimo"
    assert described.kind == kind
    assert described.related == related
    assert described.range == range_


def test_every_cell_in_a_cycle_describes_it_in_the_same_order() -> None:
    edges = (("a", ("x",), "b"), ("b", ("y",), "c"), ("c", ("z",), "a"))
    t = RunTranslator(RunId("r1"), None)
    related = []
    for cell, start in (("a", 2), ("b", 0), ("c", 1)):
        rotated = CycleError(edges_with_vars=edges[start:] + edges[:start])
        t.feed(planned(cell, "..."))
        t.feed(running(cell))
        t.feed(cell_output(cell, CellOutput.errors([rotated])))  # type: ignore[list-item]
    for completed in t.finish()[:3]:
        assert isinstance(completed, Completed)
        assert isinstance(completed.outcome, ErrorOutcome)
        related.append(completed.outcome.error.related)
    assert related[0] == related[1] == related[2]
    assert [r.cell_id for r in related[0]] == ["a", "b", "c"]


def test_a_sql_error_keeps_its_hint_and_counts_its_column_in_utf16() -> None:
    t = RunTranslator(RunId("r1"), None)
    t.feed(planned("c", 'x = "𝄞"; mo.sql("select * from t")'))
    t.feed(running("c"))
    error = MarimoSQLError(
        msg="no such table: t",
        sql_statement="select * from t",
        hint="Did you mean u?",
        node_lineno=1,
        node_col_offset=len('x = "𝄞"; '.encode()),
    )
    t.feed(cell_output("c", CellOutput.errors([error])))

    completed = t.finish()[0]
    assert isinstance(completed, Completed)
    assert isinstance(completed.outcome, ErrorOutcome)
    assert (
        completed.outcome.error.message == "no such table: t\nDid you mean u?"
    )
    assert completed.outcome.error.range == _point(
        0, len('x = "𝄞"; '.encode("utf-16-le")) // 2
    )


def test_definers_follow_the_document_when_the_translator_knows_it() -> None:
    t = RunTranslator(RunId("r1"), None, lambda: ["c", "a", "b"])
    t.feed(planned("a", "x = 1"))
    t.feed(running("a"))
    error = MultipleDefinitionError(name="x", cells=("b", "c"))
    t.feed(cell_output("a", CellOutput.errors([error])))

    completed = t.finish()[0]
    assert isinstance(completed, Completed)
    assert isinstance(completed.outcome, ErrorOutcome)
    assert [r.cell_id for r in completed.outcome.error.related] == [
        "c",
        "a",
        "b",
    ]


def test_a_conflict_reads_the_same_from_analysis_and_from_execution() -> None:
    codes = {"b": "x = 2", "a": "x = 1"}
    document = Document(
        [DocumentCell(CellId(cid), code) for cid, code in codes.items()], {}
    )
    (analyzed,) = CellAnalyzer()(document)[CellId("a")].errors

    t = RunTranslator(RunId("r1"), None, lambda: list(codes))
    t.feed(planned("a", "x = 1"))
    t.feed(running("a"))
    error = MultipleDefinitionError(name="x", cells=("b",))
    t.feed(cell_output("a", CellOutput.errors([error])))
    completed = t.finish()[0]
    assert isinstance(completed, Completed)
    assert isinstance(completed.outcome, ErrorOutcome)
    executed = completed.outcome.error

    def without_ranges(described: Error) -> Error:
        return msgspec.structs.replace(
            described,
            range=None,
            related=tuple(
                msgspec.structs.replace(r, range=None)
                for r in described.related
            ),
        )

    assert executed.range is None
    assert without_ranges(executed) == without_ranges(analyzed)
    assert [r.cell_id for r in executed.related] == ["b", "a"]


def test_an_internal_error_is_named_by_its_id() -> None:
    t = RunTranslator(RunId("r1"), "3 * 3")
    t.feed(attempt("planned"))
    t.feed(attempt("running"))
    t.feed(
        scratch(
            output=CellOutput.errors([MarimoInternalError(error_id="abc123")])
        )
    )

    completed = t.finish()[0]
    assert isinstance(completed, Completed)
    assert isinstance(completed.outcome, ErrorOutcome)
    assert completed.outcome.error.kind == "internal"
    assert completed.outcome.error.name == "abc123"
    assert "abc123" in completed.outcome.error.message
