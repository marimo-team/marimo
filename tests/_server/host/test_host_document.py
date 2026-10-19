# Copyright 2026 Marimo. All rights reserved.
"""Host edits delivered to the editor and kernel."""

from __future__ import annotations

import pytest

from marimo._ast.cell import CellConfig
from marimo._core import protocol
from marimo._core.document import Document, DocumentCell
from marimo._messaging.notebook import (
    NotebookCell,
    NotebookDocument,
    ReorderCells,
)
from marimo._messaging.notification import (
    NotebookDocumentTransactionNotification,
)
from marimo._runtime.commands import ExecuteCellCommand
from marimo._server.host.document import apply_to_session
from marimo._types.ids import CellId_t
from tests._runtime._helpers.session import mocked_kernel_session
from tests._server.host.conftest import FakeSession


def test_deleting_all_cells_broadcasts_the_final_order() -> None:
    session = FakeSession()
    session.document = NotebookDocument(
        [NotebookCell(CellId_t("a"), "x = 1", "_", CellConfig())]
    )
    document = Document([], {})

    apply_to_session(session, document)  # type: ignore[arg-type]

    notification = session.notifications[0]
    assert isinstance(notification, NotebookDocumentTransactionNotification)
    # The editor guards the last deletion; the final ordering must clear it.
    assert notification.transaction.changes[-1] == ReorderCells(cell_ids=())
    assert session.document.cell_ids == []


async def test_enabling_an_edited_cell_does_not_run_old_code() -> None:
    cell_id = CellId_t("a")
    old_code, new_code = 'print("old")', 'print("new")'
    session = FakeSession()
    session.document = NotebookDocument(
        [NotebookCell(cell_id, old_code, "_", CellConfig(disabled=True))]
    )
    document = Document([DocumentCell(cell_id, new_code)], {})

    with mocked_kernel_session(
        configs={cell_id: CellConfig(disabled=True)}
    ) as runtime:
        await runtime.kernel.run(
            [ExecuteCellCommand(cell_id=cell_id, code=old_code)]
        )
        apply_to_session(session, document)  # type: ignore[arg-type]
        for command in session.commands:
            await runtime.kernel.handle_message(command)

        assert "old" not in "".join(runtime.stdout.messages)


@pytest.mark.parametrize(
    "delete_dependent", [True, False], ids=["delete", "disable"]
)
async def test_deleted_or_disabled_cells_do_not_run_during_an_edit(
    delete_dependent: bool,
) -> None:
    first, second = CellId_t("a"), CellId_t("b")
    code = (
        'print("ran")\ntry:\n    result = x\nexcept NameError:\n    result = 0'
    )
    session = FakeSession()
    session.document = NotebookDocument(
        [
            NotebookCell(first, "x = 1", "_", CellConfig()),
            NotebookCell(second, code, "_", CellConfig()),
        ]
    )
    cells = (
        []
        if delete_dependent
        else [
            DocumentCell(
                second,
                code,
                config=protocol.CellConfig(
                    column=None,
                    disabled=True,
                    hide_code=False,
                    expand_output=False,
                ),
            )
        ]
    )
    document = Document(cells, {})

    with mocked_kernel_session() as runtime:
        await runtime.kernel.run(
            [
                ExecuteCellCommand(cell_id=first, code="x = 1"),
                ExecuteCellCommand(cell_id=second, code=code),
            ]
        )
        runtime.stdout.messages.clear()
        apply_to_session(session, document)  # type: ignore[arg-type]
        for command in session.commands:
            await runtime.kernel.handle_message(command)

        assert runtime.stdout.messages == []
