# Copyright 2026 Marimo. All rights reserved.
"""Tests for _extract_cell_data reading from the NotebookDocument.

The key change under test: `_extract_cell_data` now reads from
``session.document`` (a ``NotebookDocument``) rather than directly from
``session.app_file_manager.app.cell_manager``.  This means that
document-level mutations (applied via ``notebook-document-transaction``)
are reflected when a new client connects and receives ``kernel-ready``.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from marimo._ast.cell import CellConfig
from marimo._messaging.notebook.changes import (
    CreateCell,
    DeleteCell,
    SetCode,
    Transaction,
)
from marimo._messaging.notebook.document import NotebookCell, NotebookDocument
from marimo._server.api.endpoints.ws.ws_kernel_ready import _extract_cell_data
from marimo._types.ids import CellId_t


def _make_doc(*cells: tuple[str, str, str]) -> NotebookDocument:
    """Build a NotebookDocument from (id, code, name) triples."""
    return NotebookDocument(
        [
            NotebookCell(
                id=CellId_t(cid),
                code=code,
                name=name,
                config=CellConfig(),
            )
            for cid, code, name in cells
        ]
    )


def _manager(send_code: bool) -> MagicMock:
    mgr = MagicMock()
    mgr.should_send_code_to_frontend.return_value = send_code
    return mgr


class TestExtractCellDataFromDocument:
    """_extract_cell_data reads the document, not the cell_manager."""

    def test_empty_document(self) -> None:
        doc = NotebookDocument()
        result = _extract_cell_data(doc, _manager(send_code=True))
        assert result == ((), (), (), ())
        # Run mode should also handle empty document
        result = _extract_cell_data(doc, _manager(send_code=False))
        assert result == ((), (), (), ())

    def test_basic_extraction(self) -> None:
        doc = _make_doc(
            ("a", "x = 1", "setup"),
            ("b", "y = 2", "compute"),
        )
        codes, names, configs, cell_ids = _extract_cell_data(
            doc, _manager(send_code=True)
        )
        assert codes == ("x = 1", "y = 2")
        assert names == ("setup", "compute")
        assert cell_ids == (CellId_t("a"), CellId_t("b"))
        assert len(configs) == 2

    def test_hides_code_in_run_mode(self) -> None:
        doc = _make_doc(("a", "secret()", "fn"))
        codes, names, _, _ = _extract_cell_data(doc, _manager(send_code=False))
        assert codes == ("",)
        assert names == ("fn",)

    def test_document_mutations_reflected(self) -> None:
        """Mutations applied to the document are visible in _extract_cell_data.

        This is the core scenario: the kernel applies a transaction
        (e.g. from notebook-document-transaction) which mutates the
        document.  A subsequent call to build_kernel_ready (during
        reconnection) should see the mutated state.
        """
        doc = _make_doc(
            ("a", "x = 1", "cell_a"),
            ("b", "y = 2", "cell_b"),
            ("c", "z = 3", "cell_c"),
        )

        # Simulate a transaction that deletes cell "b" and adds a new cell
        tx = Transaction(
            changes=(
                DeleteCell(cell_id=CellId_t("b")),
                CreateCell(
                    cell_id=CellId_t("new"),
                    code="import altair",
                    name="chart",
                    config=CellConfig(hide_code=True),
                ),
            ),
            source="kernel",
        )
        doc.apply(tx)

        codes, names, configs, cell_ids = _extract_cell_data(
            doc, _manager(send_code=True)
        )
        assert cell_ids == (
            CellId_t("a"),
            CellId_t("c"),
            CellId_t("new"),
        )
        assert codes == ("x = 1", "z = 3", "import altair")
        assert names == ("cell_a", "cell_c", "chart")
        # The new cell's config should be preserved
        assert configs[2].hide_code is True

    def test_set_code_transaction_reflected(self) -> None:
        """SetCode mutations are visible on reconnection."""
        doc = _make_doc(("a", "original", "cell_a"))
        tx = Transaction(
            changes=(SetCode(cell_id=CellId_t("a"), code="modified"),),
            source="kernel",
        )
        doc.apply(tx)

        codes, _, _, _ = _extract_cell_data(doc, _manager(send_code=True))
        assert codes == ("modified",)

    def test_set_code_hidden_in_run_mode(self) -> None:
        """Even after SetCode, run-mode still hides code."""
        doc = _make_doc(("a", "original", "cell_a"))
        doc.apply(
            Transaction(
                changes=(SetCode(cell_id=CellId_t("a"), code="modified"),),
                source="kernel",
            )
        )

        codes, names, _, _ = _extract_cell_data(doc, _manager(send_code=False))
        assert codes == ("",)
        assert names == ("cell_a",)
