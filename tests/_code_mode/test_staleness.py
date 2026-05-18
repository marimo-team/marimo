# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

import pytest

from marimo._ast.cell_id import CellIdGenerator
from marimo._code_mode._context import (
    AsyncCodeModeContext,
    StaleCellError,
)
from marimo._messaging.notebook.changes import SetCode, Transaction
from marimo._messaging.notebook.document import (
    NotebookCell,
    NotebookDocument,
    notebook_document_context,
)
from marimo._runtime.commands import ExecuteCellCommand
from marimo._types.ids import CellId_t

if TYPE_CHECKING:
    from collections.abc import Generator

    from marimo._runtime.runtime import Kernel


@contextmanager
def _ctx(
    k: Kernel,
    *,
    skip_staleness_check: bool = False,
) -> Generator[AsyncCodeModeContext, None, None]:
    cells = [
        NotebookCell(id=cid, code=cell.code, name="", config=cell.config)
        for cid, cell in k.graph.cells.items()
    ]
    doc = NotebookDocument(cells)
    with notebook_document_context(doc):
        ctx = AsyncCodeModeContext(
            k, skip_staleness_check=skip_staleness_check
        )
        ctx._id_generator = CellIdGenerator(seed=7)
        ctx._id_generator.seen_ids = set(doc.cell_ids)
        yield ctx


async def _seed(k: Kernel, cell_id: str, code: str) -> None:
    await k.run([ExecuteCellCommand(cell_id=CellId_t(cell_id), code=code)])


def _bump_cell_version(doc: NotebookDocument, cell_id: str, code: str) -> None:
    doc.apply(
        Transaction(
            changes=(SetCode(cell_id=CellId_t(cell_id), code=code),),
            source="frontend",
        )
    )


class TestStalenessBlocks:
    async def test_edit_without_read_raises(self, k: Kernel) -> None:
        await _seed(k, "0", "a = 1")
        with _ctx(k) as ctx:
            async with ctx as nb:
                with pytest.raises(StaleCellError) as exc:
                    nb.edit_cell("0", "a = 2")
                assert exc.value.cell_id == CellId_t("0")
                assert CellId_t("0") in exc.value.stale_cells

    async def test_edit_after_read_succeeds(self, k: Kernel) -> None:
        await _seed(k, "0", "a = 1")
        with _ctx(k) as ctx:
            async with ctx as nb:
                _ = nb.cells["0"].code  # materialize == read
                nb.edit_cell("0", "a = 2")

    async def test_read_persists_across_contexts(self, k: Kernel) -> None:
        # kernel.agent is long-lived, so a read satisfies a future call's
        # check as long as the cell's version hasn't been bumped since.
        await _seed(k, "0", "a = 1")
        with _ctx(k) as ctx:
            async with ctx as nb:
                _ = nb.cells["0"].code

        with _ctx(k) as ctx:
            async with ctx as nb:
                nb.edit_cell("0", "a = 2")

    async def test_frontend_edit_invalidates_prior_read(
        self, k: Kernel
    ) -> None:
        await _seed(k, "0", "a = 1")
        with _ctx(k) as ctx:
            async with ctx as nb:
                _ = nb.cells["0"].code

        with _ctx(k) as ctx:
            _bump_cell_version(ctx._document, "0", "a = 99")
            async with ctx as nb:
                with pytest.raises(StaleCellError):
                    nb.edit_cell("0", "a = 2")


class TestStalenessExemptions:
    async def test_pending_add_then_edit(self, k: Kernel) -> None:
        with _ctx(k) as ctx:
            async with ctx as nb:
                cid = nb.create_cell("x = 1")
                nb.edit_cell(cid, "x = 2")

    async def test_config_only_edit_does_not_check(self, k: Kernel) -> None:
        await _seed(k, "0", "a = 1")
        with _ctx(k) as ctx:
            async with ctx as nb:
                nb.edit_cell("0", hide_code=False)

    async def test_delete_cell_not_protected(self, k: Kernel) -> None:
        await _seed(k, "0", "a = 1")
        with _ctx(k) as ctx:
            async with ctx as nb:
                nb.delete_cell("0")

    async def test_move_cell_not_protected(self, k: Kernel) -> None:
        await _seed(k, "0", "a = 1")
        await _seed(k, "1", "b = 2")
        with _ctx(k) as ctx:
            async with ctx as nb:
                nb.move_cell("0", after="1")

    async def test_skip_staleness_check_opt_out(self, k: Kernel) -> None:
        await _seed(k, "0", "a = 1")
        with _ctx(k, skip_staleness_check=True) as ctx:
            async with ctx as nb:
                nb.edit_cell("0", "a = 2")


class TestStaleCellErrorMessage:
    async def test_lists_other_stale_cells(self, k: Kernel) -> None:
        await _seed(k, "0", "a = 1")
        await _seed(k, "1", "b = 2")
        await _seed(k, "2", "c = 3")
        with _ctx(k) as ctx:
            async with ctx as nb:
                with pytest.raises(StaleCellError) as exc:
                    nb.edit_cell("0", "a = 999")
                assert exc.value.stale_cells == frozenset(
                    {CellId_t("0"), CellId_t("1"), CellId_t("2")}
                )
                msg = str(exc.value)
                assert "'0'" in msg
                assert "Other stale cells: 1, 2." in msg
                assert "skip_staleness_check=True" in msg


class TestCrossContextWriteRead:
    async def test_create_then_edit_cross_context(self, k: Kernel) -> None:
        with _ctx(k) as ctx:
            async with ctx as nb:
                cid = nb.create_cell("x = 1")
                nb.run_cell(cid)

        with _ctx(k) as ctx:
            async with ctx as nb:
                nb.edit_cell(cid, "x = 2")

    async def test_edit_then_edit_cross_context(self, k: Kernel) -> None:
        await _seed(k, "0", "a = 1")
        with _ctx(k) as ctx:
            async with ctx as nb:
                _ = nb.cells["0"].code
                nb.edit_cell("0", "a = 2")

        with _ctx(k) as ctx:
            async with ctx as nb:
                nb.edit_cell("0", "a = 3")


class TestFileWatchReload:
    async def test_replace_cells_same_code_keeps_reads_valid(
        self, k: Kernel
    ) -> None:
        from marimo._ast.cell import CellConfig

        await _seed(k, "0", "a = 1")
        with _ctx(k) as ctx:
            async with ctx as nb:
                _ = nb.cells["0"].code

        with _ctx(k) as ctx:
            ctx._document._replace_cells(
                [
                    NotebookCell(
                        id=CellId_t("0"),
                        code="a = 1",
                        name="",
                        config=CellConfig(),
                    )
                ]
            )
            async with ctx as nb:
                nb.edit_cell("0", "a = 2")

    async def test_replace_cells_changed_code_invalidates_reads(
        self, k: Kernel
    ) -> None:
        from marimo._ast.cell import CellConfig

        await _seed(k, "0", "a = 1")
        with _ctx(k) as ctx:
            async with ctx as nb:
                _ = nb.cells["0"].code

        with _ctx(k) as ctx:
            ctx._document._replace_cells(
                [
                    NotebookCell(
                        id=CellId_t("0"),
                        code="a = 100",
                        name="",
                        config=CellConfig(),
                    )
                ]
            )
            async with ctx as nb:
                with pytest.raises(StaleCellError):
                    nb.edit_cell("0", "a = 2")


class TestEmptyCellExemption:
    async def test_edit_empty_cell_without_read(self, k: Kernel) -> None:
        await _seed(k, "0", "")
        with _ctx(k) as ctx:
            async with ctx as nb:
                nb.edit_cell("0", "x = 1")

    async def test_edit_whitespace_cell_without_read(self, k: Kernel) -> None:
        await _seed(k, "0", "   \n  ")
        with _ctx(k) as ctx:
            async with ctx as nb:
                nb.edit_cell("0", "x = 1")

    async def test_non_empty_cell_still_requires_read(self, k: Kernel) -> None:
        await _seed(k, "0", "a = 1")
        with _ctx(k) as ctx:
            async with ctx as nb:
                with pytest.raises(StaleCellError):
                    nb.edit_cell("0", "x = 1")

    async def test_two_edits_on_empty_cell_same_context(
        self, k: Kernel
    ) -> None:
        await _seed(k, "0", "")
        with _ctx(k) as ctx:
            async with ctx as nb:
                nb.edit_cell("0", "x = 1")
                nb.edit_cell("0", "x = 2")

    async def test_empty_then_non_empty_edit_cross_context(
        self, k: Kernel
    ) -> None:
        # First edit lands via empty-cell exemption; the agent's own write
        # records a read, so the next-context edit passes without a fresh
        # materialization even though the cell is now non-empty.
        await _seed(k, "0", "")
        with _ctx(k) as ctx:
            async with ctx as nb:
                nb.edit_cell("0", "x = 1")
        with _ctx(k) as ctx:
            async with ctx as nb:
                nb.edit_cell("0", "x = 2")

    async def test_empty_cells_excluded_from_stale_error_list(
        self, k: Kernel
    ) -> None:
        await _seed(k, "empty", "")
        await _seed(k, "real", "a = 1")
        with _ctx(k) as ctx:
            async with ctx as nb:
                with pytest.raises(StaleCellError) as exc:
                    nb.edit_cell("real", "a = 2")
                assert exc.value.stale_cells == frozenset({CellId_t("real")})


class TestSetupCellMigration:
    async def test_rename_to_setup_without_read_raises(
        self, k: Kernel
    ) -> None:
        # The migration path silently fills `code` from `self.graph.cells`
        # when the agent passes `name="setup"` with `code=None`. Without
        # the post-migration staleness check, that fill could overwrite
        # the doc with stale graph code without ever requiring a read.
        await _seed(k, "0", "x = 1")
        with _ctx(k) as ctx:
            async with ctx as nb:
                with pytest.raises(StaleCellError):
                    nb.edit_cell("0", name="setup")

    async def test_rename_to_setup_after_read_succeeds(
        self, k: Kernel
    ) -> None:
        await _seed(k, "0", "x = 1")
        with _ctx(k) as ctx:
            async with ctx as nb:
                _ = nb.cells["0"].code
                nb.edit_cell("0", name="setup")


class TestCellsViewReadRecording:
    async def test_iteration_records_reads(self, k: Kernel) -> None:
        await _seed(k, "0", "a = 1")
        await _seed(k, "1", "b = 2")
        with _ctx(k) as ctx:
            async with ctx as nb:
                for _ in nb.cells:
                    pass
                nb.edit_cell("0", "a = 99")
                nb.edit_cell("1", "b = 99")

    async def test_find_records_reads_for_matches_only(
        self, k: Kernel
    ) -> None:
        await _seed(k, "0", "alpha = 1")
        await _seed(k, "1", "beta = 2")
        with _ctx(k) as ctx:
            async with ctx as nb:
                matches = nb.cells.find("alpha")
                assert len(matches) == 1
                nb.edit_cell("0", "alpha = 99")
                with pytest.raises(StaleCellError):
                    nb.edit_cell("1", "beta = 99")

    async def test_grep_records_reads_for_matches_only(
        self, k: Kernel
    ) -> None:
        await _seed(k, "0", "alpha = 1")
        await _seed(k, "1", "beta = 2")
        with _ctx(k) as ctx:
            async with ctx as nb:
                matches = nb.cells.grep(r"alpha")
                assert len(matches) == 1
                nb.edit_cell("0", "alpha = 99")
                with pytest.raises(StaleCellError):
                    nb.edit_cell("1", "beta = 99")
