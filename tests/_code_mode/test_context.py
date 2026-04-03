# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

if TYPE_CHECKING:
    from collections.abc import Generator

import msgspec
import pytest
from inline_snapshot import snapshot

from marimo._ast.cell import CellConfig
from marimo._ast.cell_id import CellIdGenerator
from marimo._code_mode._context import AsyncCodeModeContext
from marimo._messaging.notebook.document import (
    NotebookCell,
    NotebookDocument,
    notebook_document_context,
)
from marimo._messaging.notification import (
    NotebookDocumentTransactionNotification,
)
from marimo._runtime.commands import ExecuteCellCommand
from marimo._runtime.runtime import Kernel
from marimo._types.ids import CellId_t


@contextmanager
def _ctx(
    k: Kernel,
    extra_doc_cells: list[NotebookCell] | None = None,
) -> Generator[AsyncCodeModeContext, None, None]:
    """Build an AsyncCodeModeContext with a document snapshot from the kernel.

    ``extra_doc_cells`` adds cells to the document that are *not* in the
    kernel graph, simulating cells that exist on disk but were never run.
    """
    cells = [
        NotebookCell(id=cid, code=cell.code, name="", config=cell.config)
        for cid, cell in k.graph.cells.items()
    ]
    if extra_doc_cells:
        cells.extend(extra_doc_cells)
    doc = NotebookDocument(cells)
    with notebook_document_context(doc):
        ctx = AsyncCodeModeContext(k)
        # Use a deterministic seed in tests for snapshot stability.
        ctx._id_generator = CellIdGenerator(seed=7)
        ctx._id_generator.seen_ids = set(doc.cell_ids)
        yield ctx


def _tx_ops(k: Kernel) -> list[dict[str, object]]:
    """Serialize all document transaction ops for snapshot comparison."""
    ops: list[dict[str, object]] = []
    for notif in k.stream.operations:
        if isinstance(notif, NotebookDocumentTransactionNotification):
            ops.extend(msgspec.to_builtins(notif.transaction.changes))
    return ops


def _clear_messages(k: Kernel) -> None:
    k.stream.messages.clear()


def _graph_codes(k: Kernel) -> dict[str, str]:
    return {str(cid): cell.code for cid, cell in k.graph.cells.items()}


class TestAddCell:
    async def test_add_into_empty(self, k: Kernel) -> None:
        with _ctx(k) as ctx:
            _clear_messages(k)

            async with ctx as nb:
                cid = nb.create_cell("x = 1")
                nb.run_cell(cid)

            assert len(k.graph.cells) == 1
            cell = next(iter(k.graph.cells.values()))
            assert cell.code == "x = 1"
            assert k.globals["x"] == 1

            assert _tx_ops(k) == snapshot(
                [
                    {
                        "type": "create-cell",
                        "cellId": "qhHd",
                        "code": "x = 1",
                        "name": "",
                        "config": {
                            "column": None,
                            "disabled": False,
                            "hide_code": True,
                        },
                        "before": None,
                        "after": None,
                    },
                    {"type": "reorder-cells", "cellIds": ("qhHd",)},
                ]
            )

    async def test_add_appends_by_default(self, k: Kernel) -> None:
        await k.run(
            [
                ExecuteCellCommand(cell_id=CellId_t("0"), code="a = 10"),
                ExecuteCellCommand(cell_id=CellId_t("1"), code="b = 20"),
            ]
        )
        with _ctx(k) as ctx:
            _clear_messages(k)

            async with ctx as nb:
                cid = nb.create_cell("c = a + b")
                nb.run_cell(cid)

            assert len(k.graph.cells) == 3
            assert k.globals["c"] == 30

            # New cell should be last in the ordering.
            ops = _tx_ops(k)
            reorder = [o for o in ops if o["type"] == "reorder-cells"]
            assert len(reorder) == 1
            assert reorder[0]["cellIds"][:2] == ("0", "1")
            assert len(reorder[0]["cellIds"]) == 3

    async def test_add_with_after(self, k: Kernel) -> None:
        await k.run(
            [
                ExecuteCellCommand(cell_id=CellId_t("0"), code="a = 10"),
                ExecuteCellCommand(cell_id=CellId_t("1"), code="b = 20"),
            ]
        )
        with _ctx(k) as ctx:
            _clear_messages(k)

            async with ctx as nb:
                nb.create_cell("c = a + b", after="0")

            ops = _tx_ops(k)
            reorder = next(o for o in ops if o["type"] == "reorder-cells")
            assert reorder["cellIds"][0] == "0"
            # New cell should be after "0", before "1".
            assert reorder["cellIds"][2] == "1"

    async def test_add_without_run_does_not_execute(self, k: Kernel) -> None:
        with _ctx(k) as ctx:
            _clear_messages(k)

            async with ctx as nb:
                nb.create_cell("x = 999")

            assert len(k.graph.cells) == 1
            assert "x" not in k.globals

            # Cell should appear as a CreateCell op (frontend marks it stale).
            ops = _tx_ops(k)
            creates = [o for o in ops if o["type"] == "create-cell"]
            assert len(creates) == 1
            assert creates[0]["code"] == "x = 999"

    async def test_add_returns_cell_id(self, k: Kernel) -> None:
        with _ctx(k) as ctx:
            async with ctx as nb:
                cid = nb.create_cell("x = 1")
                assert isinstance(cid, str)
                assert len(cid) > 0

    async def test_add_chain_after(self, k: Kernel) -> None:
        """Can reference a just-added cell's ID in a subsequent add."""
        with _ctx(k) as ctx:
            async with ctx as nb:
                cid1 = nb.create_cell("x = 1")
                cid2 = nb.create_cell("y = 2", after=cid1)
                nb.run_cell(cid1)
                nb.run_cell(cid2)

            assert k.globals["x"] == 1
            assert k.globals["y"] == 2


class TestDeleteCell:
    async def test_delete_cell(self, k: Kernel) -> None:
        await k.run(
            [
                ExecuteCellCommand(cell_id=CellId_t("0"), code="a = 1"),
                ExecuteCellCommand(cell_id=CellId_t("1"), code="b = 2"),
                ExecuteCellCommand(cell_id=CellId_t("2"), code="c = 3"),
            ]
        )
        assert len(k.graph.cells) == 3

        with _ctx(k) as ctx:
            _clear_messages(k)

            async with ctx as nb:
                nb.delete_cell("1")

            assert _graph_codes(k) == snapshot({"0": "a = 1", "2": "c = 3"})

            assert _tx_ops(k) == snapshot(
                [
                    {"type": "delete-cell", "cellId": "1"},
                    {"type": "reorder-cells", "cellIds": ("0", "2")},
                ]
            )

    async def test_delete_cleans_globals(self, k: Kernel) -> None:
        """Deleting a cell removes its defs from kernel globals."""
        await k.run(
            [
                ExecuteCellCommand(cell_id=CellId_t("0"), code="a = 1"),
                ExecuteCellCommand(cell_id=CellId_t("1"), code="b = 2"),
            ]
        )
        assert k.globals["a"] == 1
        assert k.globals["b"] == 2

        with _ctx(k) as ctx:
            async with ctx as nb:
                nb.delete_cell("1")

            assert k.globals["a"] == 1
            assert "b" not in k.globals

    async def test_delete_multiple(self, k: Kernel) -> None:
        await k.run(
            [
                ExecuteCellCommand(cell_id=CellId_t("0"), code="a = 1"),
                ExecuteCellCommand(cell_id=CellId_t("1"), code="b = 2"),
                ExecuteCellCommand(cell_id=CellId_t("2"), code="c = 3"),
            ]
        )
        with _ctx(k) as ctx:
            _clear_messages(k)

            async with ctx as nb:
                nb.delete_cell("0")
                nb.delete_cell("2")

            assert _graph_codes(k) == snapshot({"1": "b = 2"})


class TestUpdateCell:
    async def test_update_code(self, k: Kernel) -> None:
        await k.run([ExecuteCellCommand(cell_id=CellId_t("0"), code="x = 1")])
        assert k.globals["x"] == 1

        with _ctx(k) as ctx:
            _clear_messages(k)

            async with ctx as nb:
                nb.edit_cell("0", code="x = 42")
                nb.run_cell("0")

            assert k.globals["x"] == 42
            assert _graph_codes(k) == snapshot({"0": "x = 42"})

            assert _tx_ops(k) == snapshot(
                [
                    {"type": "set-code", "cellId": "0", "code": "x = 42"},
                    {"type": "reorder-cells", "cellIds": ("0",)},
                ]
            )

    async def test_update_cleans_stale_globals(self, k: Kernel) -> None:
        """Updating code removes old defs that are no longer defined."""
        await k.run(
            [ExecuteCellCommand(cell_id=CellId_t("0"), code="x = 1\ny = 2")]
        )
        assert k.globals["x"] == 1
        assert k.globals["y"] == 2

        with _ctx(k) as ctx:
            async with ctx as nb:
                nb.edit_cell("0", code="x = 42")
                nb.run_cell("0")

            assert k.globals["x"] == 42
            assert "y" not in k.globals

    async def test_update_preserves_config(self, k: Kernel) -> None:
        """Updating only code preserves the cell's existing config."""
        await k.run([ExecuteCellCommand(cell_id=CellId_t("0"), code="x = 1")])

        # Set hide_code=True on the cell.
        with _ctx(k) as ctx:
            async with ctx as nb:
                nb.edit_cell("0", hide_code=True)

        assert k.cell_metadata["0"].config.hide_code is True

        # Update code without touching config — hide_code should stick.
        with _ctx(k) as ctx:
            async with ctx as nb:
                nb.edit_cell("0", code="x = 42")
                nb.run_cell("0")

        assert k.globals["x"] == 42
        assert k.cell_metadata["0"].config.hide_code is True

    async def test_update_config_only(self, k: Kernel) -> None:
        await k.run([ExecuteCellCommand(cell_id=CellId_t("0"), code="x = 1")])

        with _ctx(k) as ctx:
            _clear_messages(k)

            async with ctx as nb:
                nb.edit_cell("0", hide_code=True)

            assert k.globals["x"] == 1
            assert _graph_codes(k) == snapshot({"0": "x = 1"})
            assert _tx_ops(k) == snapshot(
                [
                    {
                        "type": "set-config",
                        "cellId": "0",
                        "column": None,
                        "disabled": False,
                        "hideCode": True,
                    },
                    {"type": "reorder-cells", "cellIds": ("0",)},
                ]
            )


class TestCombined:
    async def test_delete_and_add(self, k: Kernel) -> None:
        await k.run(
            [
                ExecuteCellCommand(cell_id=CellId_t("0"), code="a = 1"),
                ExecuteCellCommand(cell_id=CellId_t("1"), code="b = 2"),
                ExecuteCellCommand(cell_id=CellId_t("2"), code="c = 3"),
            ]
        )

        with _ctx(k) as ctx:
            _clear_messages(k)

            async with ctx as nb:
                nb.delete_cell("1")
                cid = nb.create_cell("d = a + c", after="0")
                nb.run_cell(cid)

            assert k.globals["d"] == 4
            codes = _graph_codes(k)
            assert "1" not in codes

    async def test_delete_and_add_same_defs(self, k: Kernel) -> None:
        """Delete a cell and add a replacement defining the same names."""
        await k.run(
            [
                ExecuteCellCommand(cell_id=CellId_t("0"), code="a = 1"),
                ExecuteCellCommand(cell_id=CellId_t("1"), code="b = a + 1"),
            ]
        )
        assert k.globals["b"] == 2

        with _ctx(k) as ctx:
            _clear_messages(k)

            # Delete cell "1" and create a new cell that also defines "b".
            # This must not raise a multiply-defined error.
            async with ctx as nb:
                nb.delete_cell("1")
                cid = nb.create_cell("b = a + 100")
                nb.run_cell(cid)

            assert k.globals["b"] == 101
            assert "1" not in _graph_codes(k)

    async def test_noop_batch(self, k: Kernel) -> None:
        """An empty context manager does nothing."""
        await k.run([ExecuteCellCommand(cell_id=CellId_t("0"), code="x = 1")])
        with _ctx(k) as ctx:
            _clear_messages(k)

            async with ctx as nb:
                pass

            assert _graph_codes(k) == snapshot({"0": "x = 1"})

    async def test_exception_discards_ops(self, k: Kernel) -> None:
        """If an exception occurs, queued ops are discarded."""
        await k.run([ExecuteCellCommand(cell_id=CellId_t("0"), code="x = 1")])
        with _ctx(k) as ctx:
            try:
                async with ctx as nb:
                    nb.create_cell("y = 2")
                    raise ValueError("oops")
            except ValueError:
                pass

            # The add should not have been applied.
            assert _graph_codes(k) == snapshot({"0": "x = 1"})
            assert len(k.graph.cells) == 1

    async def test_rerun_without_structural_ops(self, k: Kernel) -> None:
        """run_cell without any create/edit/delete still executes."""
        await k.run([ExecuteCellCommand(cell_id=CellId_t("0"), code="x = 1")])
        with _ctx(k) as ctx:
            # Mutate the global so we can detect re-execution.
            k.globals["x"] = 0
            async with ctx as nb:
                nb.run_cell("0")

            assert k.globals["x"] == 1

    async def test_rerun_alongside_structural_ops(self, k: Kernel) -> None:
        """run_cell on an unchanged cell works even with other structural ops."""
        await k.run(
            [
                ExecuteCellCommand(cell_id=CellId_t("0"), code="x = 1"),
                ExecuteCellCommand(cell_id=CellId_t("1"), code="y = x + 1"),
            ]
        )
        with _ctx(k) as ctx:
            # Mutate so we can detect re-execution of "0".
            k.globals["x"] = 0
            async with ctx as nb:
                nb.create_cell("z = 99", name="new")
                nb.run_cell("0")

            assert k.globals["x"] == 1

    async def test_run_deleted_cell_raises(self, k: Kernel) -> None:
        """Calling run_cell on a cell queued for deletion raises."""
        await k.run([ExecuteCellCommand(cell_id=CellId_t("0"), code="x = 1")])
        with _ctx(k) as ctx:
            async with ctx as nb:
                nb.delete_cell("0")
                with pytest.raises(ValueError, match="queued for deletion"):
                    nb.run_cell("0")


class TestSummary:
    async def test_create_prints_summary(
        self, k: Kernel, capsys: object
    ) -> None:
        with _ctx(k) as ctx:
            async with ctx as nb:
                nb.create_cell("x = 1", name="my_cell")

            captured = capsys.readouterr()  # type: ignore[attr-defined]
            assert captured.out == snapshot("created cell 'qhHd' (my_cell)\n")

    async def test_edit_prints_summary(
        self, k: Kernel, capsys: object
    ) -> None:
        await k.run([ExecuteCellCommand(cell_id=CellId_t("0"), code="x = 1")])
        with _ctx(k) as ctx:
            async with ctx as nb:
                nb.edit_cell("0", code="x = 2")

            captured = capsys.readouterr()  # type: ignore[attr-defined]
            assert captured.out == snapshot("edited code of cell '0'\n")

    async def test_delete_prints_summary(
        self, k: Kernel, capsys: object
    ) -> None:
        await k.run([ExecuteCellCommand(cell_id=CellId_t("0"), code="x = 1")])
        with _ctx(k) as ctx:
            async with ctx as nb:
                nb.delete_cell("0")

            captured = capsys.readouterr()  # type: ignore[attr-defined]
            assert captured.out == snapshot("deleted cell '0'\n")

    async def test_noop_prints_nothing(
        self, k: Kernel, capsys: object
    ) -> None:
        with _ctx(k) as ctx:
            async with ctx as nb:
                pass

            captured = capsys.readouterr()  # type: ignore[attr-defined]
            assert captured.out == ""

    async def test_batch_summary(self, k: Kernel, capsys: object) -> None:
        """Full batch: create+run, edit+run, delete, create (staged), re-run."""
        await k.run(
            [
                ExecuteCellCommand(cell_id=CellId_t("0"), code="a = 1"),
                ExecuteCellCommand(cell_id=CellId_t("1"), code="b = 2"),
                ExecuteCellCommand(cell_id=CellId_t("2"), code="c = 3"),
            ]
        )
        with _ctx(k) as ctx:
            async with ctx as nb:
                # delete
                nb.delete_cell("1")
                # create + run
                nb.create_cell("d = 4", name="new_cell")
                nb.run_cell("new_cell")
                # create without run (staged)
                nb.create_cell("e = 5", name="staged")
                # edit + run
                nb.edit_cell("0", code="a = 10")
                nb.run_cell("0")
                # re-run existing cell without editing
                nb.run_cell("2")

            captured = capsys.readouterr()  # type: ignore[attr-defined]
            assert captured.out == snapshot("""\
deleted cell '1'
created and ran cell 'qhHd' (new_cell)
created cell 'BtdA' (staged)
edited code of cell '0' and ran
re-ran cell '2'
""")


class TestResolveTarget:
    async def test_create_after_pending_add_by_name(self, k: Kernel) -> None:
        """Can reference a just-added cell by name in a subsequent add."""
        with _ctx(k) as ctx:
            async with ctx as nb:
                cid1 = nb.create_cell("x = 1", name="first")
                cid2 = nb.create_cell("y = x + 1", after="first")
                nb.run_cell(cid1)
                nb.run_cell(cid2)

            assert k.globals["x"] == 1
            assert k.globals["y"] == 2

            # "first" should come before the second cell in ordering.
            ops = _tx_ops(k)
            reorder = next(o for o in ops if o["type"] == "reorder-cells")
            assert len(reorder["cellIds"]) == 2

    async def test_create_after_renamed_cell(self, k: Kernel) -> None:
        """Can reference a cell by its new name after edit_cell renames it."""
        await k.run(
            [
                ExecuteCellCommand(cell_id=CellId_t("0"), code="a = 1"),
                ExecuteCellCommand(cell_id=CellId_t("1"), code="b = 2"),
            ]
        )
        with _ctx(k) as ctx:
            _clear_messages(k)

            async with ctx as nb:
                nb.edit_cell("0", name="renamed")
                cid = nb.create_cell("c = a + b", after="renamed")
                nb.run_cell(cid)

            assert k.globals["c"] == 3

            # New cell should be after "0" (renamed), before "1".
            ops = _tx_ops(k)
            reorder = next(o for o in ops if o["type"] == "reorder-cells")
            assert reorder["cellIds"][0] == "0"
            assert reorder["cellIds"][2] == "1"


class TestInstallPackages:
    async def test_install_single(self, k: Kernel) -> None:
        with _ctx(k) as ctx:
            pm = k.packages_callbacks.package_manager
            assert pm is not None

            with patch.object(
                pm, "install", new_callable=AsyncMock, return_value=True
            ) as mock_install:
                async with ctx:
                    ctx.install_packages("pandas")
                    # Not installed yet — still queued.
                    assert mock_install.call_count == 0

            assert mock_install.call_count == 1
            assert mock_install.call_args_list[0].args[0] == "pandas"
            assert mock_install.call_args_list[0].kwargs["version"] == ""

    async def test_install_multiple_with_specifiers(self, k: Kernel) -> None:
        with _ctx(k) as ctx:
            pm = k.packages_callbacks.package_manager
            assert pm is not None

            with patch.object(
                pm, "install", new_callable=AsyncMock, return_value=True
            ) as mock_install:
                async with ctx:
                    ctx.install_packages(
                        "pandas", "polars>=0.20", "numpy==1.26"
                    )

            # Each package should have been installed one-by-one.
            installed = {
                call.args[0]: call.kwargs["version"]
                for call in mock_install.call_args_list
            }
            assert installed["pandas"] == ""
            assert installed["polars>=0.20"] == ""
            assert installed["numpy==1.26"] == ""


class TestAutorunStaleState:
    """In autorun mode, downstream cells should not be marked stale."""

    async def test_dependent_chain_only_root_run(self, k: Kernel) -> None:
        """Running the root cell should mark reactive descendants as
        non-stale in autorun mode so the frontend doesn't show them
        as 'needs run'."""
        with _ctx(k) as ctx:
            _clear_messages(k)

            async with ctx as nb:
                a = nb.create_cell("x = 1")
                b = nb.create_cell("y = x + 1")
                nb.run_cell(a)

            # Both cells should have executed.
            assert k.globals["x"] == 1
            assert k.globals["y"] == 2

            # Both cells should appear as CreateCell ops in the transaction.
            ops = _tx_ops(k)
            creates = [o for o in ops if o["type"] == "create-cell"]
            assert len(creates) == 2
            assert creates[0]["code"] == "x = 1"
            assert creates[1]["code"] == "y = x + 1"

    async def test_dependent_chain_lazy_mode(
        self, lazy_kernel: Kernel
    ) -> None:
        """In lazy mode, only the explicitly run cell should be non-stale.
        Downstream cells stay stale."""
        k = lazy_kernel
        with _ctx(k) as ctx:
            _clear_messages(k)

            async with ctx as nb:
                a = nb.create_cell("x = 1")
                b = nb.create_cell("y = x + 1")
                nb.run_cell(a)

            assert k.globals["x"] == 1
            # b should NOT have executed in lazy mode.
            assert "y" not in k.globals

            # Both cells should appear as CreateCell ops in the transaction.
            ops = _tx_ops(k)
            creates = [o for o in ops if o["type"] == "create-cell"]
            assert len(creates) == 2
            assert creates[0]["code"] == "x = 1"
            assert creates[1]["code"] == "y = x + 1"

    async def test_two_step_edit_then_run(self, k: Kernel) -> None:
        """edit_cell in one flush, run_cell in a separate flush should
        execute the updated code."""
        await k.run([ExecuteCellCommand(cell_id=CellId_t("0"), code="x = 1")])

        # Flush 1: edit only
        with _ctx(k) as ctx:
            async with ctx as nb:
                nb.edit_cell("0", code="x = 42")

        _clear_messages(k)

        # Flush 2: run only
        with _ctx(k) as ctx:
            async with ctx as nb:
                nb.run_cell("0")

        assert k.globals["x"] == 42


class TestDocumentKernelDivergence:
    """Tests for cells that exist in the document but not in the kernel graph."""

    async def test_delete_doc_only_cell(self, k: Kernel) -> None:
        """Deleting a cell that is in the document but not the kernel
        graph should succeed without KeyError."""
        ghost = NotebookCell(
            id=CellId_t("ghost"), code="y = 99", name="", config=CellConfig()
        )
        with _ctx(k, extra_doc_cells=[ghost]) as ctx:
            async with ctx as nb:
                nb.delete_cell("ghost")

        # The ghost cell should not appear in the graph.
        assert "ghost" not in k.graph.cells

    async def test_edit_and_run_doc_only_cell(self, k: Kernel) -> None:
        """A cell present only in the document can be edited and run,
        bringing it into the kernel graph."""
        ghost = NotebookCell(
            id=CellId_t("ghost"), code="z = 0", name="", config=CellConfig()
        )
        with _ctx(k, extra_doc_cells=[ghost]) as ctx:
            async with ctx as nb:
                nb.edit_cell("ghost", code="z = 42")
                nb.run_cell("ghost")

        assert k.globals["z"] == 42

    async def test_create_cell_no_collision_with_doc_only_ids(
        self, k: Kernel
    ) -> None:
        """create_cell must not generate IDs that collide with cells
        that exist in the document but not in the kernel graph (B4)."""
        # Build a large set of document-only cells whose IDs come from
        # the same deterministic seed used by the test helper.
        gen = CellIdGenerator(seed=7)
        doc_only: list[NotebookCell] = []
        for _ in range(60):
            cid = gen.create_cell_id()
            doc_only.append(
                NotebookCell(id=cid, code="pass", name="", config=CellConfig())
            )

        with _ctx(k, extra_doc_cells=doc_only) as ctx:
            async with ctx as nb:
                # Should not raise ValueError from ID collision.
                new_id = nb.create_cell("x = 1")

        assert new_id not in {c.id for c in doc_only}


class TestErrorReporting:
    async def test_print_summary_reports_cell_errors(
        self, k: Kernel, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """_print_summary writes cell runtime errors to stderr."""
        with _ctx(k) as ctx:
            async with ctx as nb:
                cid = nb.create_cell("raise ValueError('boom')")
                nb.run_cell(cid)

        captured = capsys.readouterr()
        assert "error in cell" in captured.err
        assert "boom" in captured.err
