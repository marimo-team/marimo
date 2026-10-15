# Copyright 2026 Marimo. All rights reserved.
"""Host edits delivered to the editor and kernel."""

from __future__ import annotations

from marimo._ast.cell import CellConfig
from marimo._core import protocol
from marimo._core.document import Document
from marimo._messaging.notebook import (
    NotebookCell,
    NotebookDocument,
    ReorderCells,
)
from marimo._messaging.notification import (
    NotebookDocumentTransactionNotification,
)
from marimo._server.host.document import apply_to_session
from marimo._types.ids import CellId_t
from tests._server.host.conftest import FakeSession


def test_deleting_all_cells_broadcasts_the_final_order() -> None:
    session = FakeSession()
    session.document = NotebookDocument(
        [NotebookCell(CellId_t("a"), "x = 1", "_", CellConfig())]
    )
    document = Document(protocol.NotebookId("nb"), [], {})

    apply_to_session(session, document)  # type: ignore[arg-type]

    notification = session.notifications[0]
    assert isinstance(notification, NotebookDocumentTransactionNotification)
    # The editor guards the last deletion; the final ordering must clear it.
    assert notification.transaction.changes[-1] == ReorderCells(cell_ids=())
    assert session.document.cell_ids == []
