# Copyright 2026 Marimo. All rights reserved.
"""Results restored from the outputs a session stored beside a notebook."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from marimo._core import protocol
from marimo._core.document import DocumentCell
from marimo._server.host.restore import (
    executions_from_session,
    restored_executions,
)
from marimo._session.state.serialize import get_session_cache_file
from marimo._utils.code import hash_code
from marimo._version import __version__

if TYPE_CHECKING:
    from pathlib import Path

    from marimo._schemas.session import (
        Cell,
        ConsoleType,
        NotebookSessionV1,
        OutputType,
    )


def cell(cell_id: str, code: str) -> DocumentCell:
    return DocumentCell(protocol.CellId(cell_id), code)


def stored(
    code: str,
    outputs: list[OutputType] | None = None,
    console: list[ConsoleType] | None = None,
) -> Cell:
    """A cell as a session stores it, under whatever id it had then."""
    return {
        "id": "earlier",
        "code_hash": hash_code(code),
        "outputs": outputs or [],
        "console": console or [],
    }


def session(
    *cells: Cell, version: str = __version__, script: str | None = None
) -> NotebookSessionV1:
    return {
        "version": "1",
        "metadata": {
            "marimo_version": version,
            "script_metadata_hash": script,
        },
        "cells": list(cells),
    }


def shown(text: str) -> list[OutputType]:
    return [{"type": "data", "data": {"text/plain": text}}]


def test_a_stored_output_is_a_completed_execution_of_no_run() -> None:
    document = [cell("a", "print('hello')\n42")]

    executions = executions_from_session(
        session(
            stored(
                "print('hello')\n42",
                shown("42"),
                [
                    {
                        "type": "stream",
                        "name": "stdout",
                        "text": "hello\n",
                        "mimetype": "text/plain",
                    },
                    {
                        "type": "streamMedia",
                        "name": "media",
                        "data": "data:image/png;base64,",
                        "mimetype": "image/png",
                    },
                    {
                        "type": "stream",
                        "name": "stderr",
                        "text": "careful\n",
                        "mimetype": "text/plain",
                    },
                ],
            )
        ),
        document,
    )

    restored = executions.current(protocol.CellId("a"))
    assert restored is not None
    execution = restored.execution
    assert execution == protocol.Execution(
        id=execution.id,
        run_id=None,
        runtime_id=None,
        caused_by=None,
        cell_id=protocol.CellId("a"),
        code=None,
        code_fingerprint=protocol.CodeFingerprint(
            document[0].code_fingerprint
        ),
        depends_on={},
        status="completed",
        outcome=protocol.ValueOutcome(
            protocol.DisplayData(mimetype="text/plain", data="42")
        ),
        started_at=None,
        completed_at=None,
    )
    # Text and media keep the order they were written in.
    assert restored.outputs == (
        protocol.Console(
            execution.id, restored.outputs[0].id, "stdout", 0, "hello\n"
        ),
        protocol.Display(
            protocol.DisplayData(
                mimetype="image/png", data="data:image/png;base64,"
            ),
            execution.id,
            restored.outputs[1].id,
            1,
        ),
        protocol.Console(
            execution.id, restored.outputs[2].id, "stderr", 2, "careful\n"
        ),
    )
    assert len({item.id for item in restored.outputs}) == 3
    assert restored.variables == ()


def test_a_stored_error_keeps_its_type_message_and_traceback() -> None:
    executions = executions_from_session(
        session(
            stored(
                "1 / 0",
                [
                    {
                        "type": "error",
                        "ename": "ZeroDivisionError",
                        "evalue": "division by zero",
                        "traceback": ["Traceback", "ZeroDivisionError"],
                    }
                ],
            )
        ),
        [cell("a", "1 / 0")],
    )

    restored = executions.current(protocol.CellId("a"))
    assert restored is not None
    assert restored.execution.outcome == protocol.ErrorOutcome(
        protocol.Error(
            kind="exception",
            name="ZeroDivisionError",
            message="division by zero",
            traceback=protocol.DisplayData(
                mimetype="text/plain", data="Traceback\nZeroDivisionError"
            ),
            source="marimo",
            severity="error",
            range=None,
            related=(),
        )
    )


def failed(ename: str, evalue: str) -> list[OutputType]:
    return [
        {"type": "error", "ename": ename, "evalue": evalue, "traceback": []}
    ]


def outcome_of(outputs: list[OutputType]) -> protocol.Outcome | None:
    executions = executions_from_session(
        session(stored("x", outputs)), [cell("a", "x")]
    )
    restored = executions.current(protocol.CellId("a"))
    assert restored is not None
    return restored.execution.outcome


def test_a_stored_kernel_error_is_the_outcome_a_live_run_reports() -> None:
    # A session stores every kernel error as a type tag and a message. A
    # cell that was interrupted, or never ran, must not come back as one
    # that raised.
    assert (
        outcome_of(failed("interruption", "This cell was interrupted"))
        == protocol.InterruptedOutcome()
    )
    assert outcome_of(
        failed("ancestor-stopped", "An ancestor stopped: ")
    ) == protocol.SkippedOutcome(
        reason="upstream-stopped",
        message="An ancestor stopped",
        related=(
            protocol.Related(
                cell_id=protocol.CellId("a"), range=None, message="Did not run"
            ),
        ),
    )
    conflict = outcome_of(failed("multiple-defs", "x was defined twice"))
    assert isinstance(conflict, protocol.ErrorOutcome)
    assert (conflict.error.kind, conflict.error.name) == (
        "multiple-definitions",
        None,
    )


def test_stored_values_and_text_keep_their_formats() -> None:
    bundle = {"text/html": "<b>1</b>", "text/plain": "1"}
    highlighted = '<span class="codehilite">Traceback</span>'
    executions = executions_from_session(
        session(
            stored("x", [{"type": "data", "data": bundle}]),
            stored(
                "y",
                [
                    {
                        "type": "error",
                        "ename": "ValueError",
                        "evalue": "bad",
                        "traceback": [highlighted],
                    }
                ],
                [
                    {
                        "type": "stream",
                        "name": "stdout",
                        "text": "secret",
                        "mimetype": "text/password",
                    },
                    {
                        "type": "stream",
                        "name": "stderr",
                        "text": highlighted,
                        "mimetype": "application/vnd.marimo+traceback",
                    },
                ],
            ),
        ),
        [cell("a", "x"), cell("b", "y")],
    )

    value = executions.current(protocol.CellId("a"))
    assert value is not None
    assert value.execution.outcome == protocol.ValueOutcome(
        protocol.DisplayData(
            mimetype="application/vnd.marimo+mimebundle",
            data=json.dumps(bundle),
        )
    )
    raised = executions.current(protocol.CellId("b"))
    assert raised is not None
    assert isinstance(raised.execution.outcome, protocol.ErrorOutcome)
    assert raised.execution.outcome.error.traceback == protocol.DisplayData(
        mimetype="text/html", data=highlighted
    )
    # An old password entry is dropped, and the rendered traceback is a
    # display, not console text.
    assert raised.outputs == (
        protocol.Display(
            protocol.DisplayData(
                mimetype="application/vnd.marimo+traceback", data=highlighted
            ),
            raised.execution.id,
            raised.outputs[0].id,
            0,
        ),
    )


def test_stored_cells_follow_the_documents_order() -> None:
    # Two cells with the same code keep their own outputs, a cell whose
    # code is not the stored one gets none, and neither does a cell that
    # stored nothing to show.
    executions = executions_from_session(
        session(
            stored("x", shown("first")),
            stored("x", shown("second")),
            stored("before an edit", shown("stale")),
            stored("y = 1"),
            stored("z", shown("")),
        ),
        [
            cell("a", "x"),
            cell("b", "x"),
            cell("c", "after an edit"),
            cell("d", "y = 1"),
            cell("e", "z"),
        ],
    )

    def display(cell_id: str) -> str | None:
        result = executions.current(protocol.CellId(cell_id))
        if result is None:
            return None
        outcome = result.execution.outcome
        assert isinstance(outcome, protocol.ValueOutcome)
        assert outcome.display is not None
        return outcome.display.data

    assert [display(cell_id) for cell_id in "abcde"] == [
        "first",
        "second",
        None,
        None,
        None,
    ]


def write(file: Path, contents: str) -> None:
    file.write_text("import marimo\napp = marimo.App()\n")
    cache = get_session_cache_file(file)
    cache.parent.mkdir(parents=True)
    cache.write_text(contents)


def test_results_stored_beside_a_file_are_restored(tmp_path: Path) -> None:
    file = tmp_path / "notebook.py"
    write(file, json.dumps(session(stored("x", shown("1")), stored("y"))))

    executions = restored_executions(file, [cell("a", "x"), cell("b", "y")])

    assert executions.current(protocol.CellId("a")) is not None
    assert executions.current(protocol.CellId("b")) is None


@pytest.mark.parametrize(
    "contents",
    [
        # One cell's code changed, so the others' outputs may not hold.
        json.dumps(session(stored("x", shown("1")), stored("y before"))),
        # A cell was added.
        json.dumps(session(stored("x", shown("1")))),
        json.dumps(
            session(stored("x", shown("1")), stored("y"), version="0.0.0")
        ),
        # The script's dependencies changed since the outputs were stored.
        json.dumps(
            session(stored("x", shown("1")), stored("y"), script="other")
        ),
        "not json",
        None,
    ],
    ids=[
        "edited",
        "added",
        "another-version",
        "other-dependencies",
        "unreadable",
        "missing",
    ],
)
def test_results_that_do_not_describe_the_cells_are_not_restored(
    tmp_path: Path, contents: str | None
) -> None:
    file = tmp_path / "notebook.py"
    if contents is None:
        file.write_text("import marimo\napp = marimo.App()\n")
    else:
        write(file, contents)

    executions = restored_executions(file, [cell("a", "x"), cell("b", "y")])

    assert executions.current(protocol.CellId("a")) is None
