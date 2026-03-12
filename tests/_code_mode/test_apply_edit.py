# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from inline_snapshot import snapshot

from marimo._ast.cell import CellConfig
from marimo._code_mode._context import AsyncCodeModeContext
from marimo._code_mode._edits import NotebookCellData, NotebookEdit
from marimo._messaging.notification import (
    UpdateCellCodesNotification,
    UpdateCellIdsNotification,
)
from marimo._runtime.commands import ExecuteCellCommand
from marimo._runtime.runtime import Kernel


def _notification_summary(
    stream: object,
) -> list[dict[str, object]]:
    """Extract code-mode-relevant notifications from the mock stream."""
    results: list[dict[str, object]] = []
    for op in stream.operations:  # type: ignore[attr-defined]
        if isinstance(op, UpdateCellCodesNotification):
            results.append(
                {
                    "op": "update-cell-codes",
                    "cell_ids": list(op.cell_ids),
                    "codes": list(op.codes),
                    "stale": op.code_is_stale,
                }
            )
        elif isinstance(op, UpdateCellIdsNotification):
            results.append(
                {
                    "op": "update-cell-ids",
                    "cell_ids": list(op.cell_ids),
                }
            )
    return results


def _clear_messages(stream: object) -> None:
    stream.messages.clear()  # type: ignore[attr-defined]


def _graph_codes(k: Kernel) -> dict[str, str]:
    return {str(cid): cell.code for cid, cell in k.graph.cells.items()}


class TestApplyEditInsert:
    async def test_insert_into_empty(self, k: Kernel) -> None:
        ctx = AsyncCodeModeContext(k)
        _clear_messages(k.stream)

        await ctx.apply_edit(
            NotebookEdit.insert_cells(0, [NotebookCellData(code="x = 1")])
        )

        assert len(k.graph.cells) == 1
        cell = list(k.graph.cells.values())[0]
        assert cell.code == "x = 1"
        assert k.globals["x"] == 1

        notifs = _notification_summary(k.stream)
        assert any(n["op"] == "update-cell-codes" for n in notifs)
        assert any(n["op"] == "update-cell-ids" for n in notifs)

    async def test_insert_into_existing(self, k: Kernel) -> None:
        await k.run(
            [
                ExecuteCellCommand(cell_id="0", code="a = 10"),
                ExecuteCellCommand(cell_id="1", code="b = 20"),
            ]
        )
        assert _graph_codes(k) == snapshot({"0": "a = 10", "1": "b = 20"})

        ctx = AsyncCodeModeContext(k)
        _clear_messages(k.stream)

        await ctx.apply_edit(
            NotebookEdit.insert_cells(1, [NotebookCellData(code="c = a + b")])
        )

        assert len(k.graph.cells) == 3
        assert k.globals["c"] == 30

    async def test_insert_draft_does_not_execute(self, k: Kernel) -> None:
        ctx = AsyncCodeModeContext(k)
        _clear_messages(k.stream)

        await ctx.apply_edit(
            NotebookEdit.insert_cells(
                0, [NotebookCellData(code="x = 999", draft=True)]
            )
        )

        assert len(k.graph.cells) == 1
        assert "x" not in k.globals

        notifs = _notification_summary(k.stream)
        code_notifs = [n for n in notifs if n["op"] == "update-cell-codes"]
        assert len(code_notifs) == 1
        assert code_notifs[0]["codes"] == ["x = 999"]
        assert code_notifs[0]["stale"] is True


class TestApplyEditDelete:
    async def test_delete_cell(self, k: Kernel) -> None:
        await k.run(
            [
                ExecuteCellCommand(cell_id="0", code="a = 1"),
                ExecuteCellCommand(cell_id="1", code="b = 2"),
                ExecuteCellCommand(cell_id="2", code="c = 3"),
            ]
        )
        assert len(k.graph.cells) == 3

        ctx = AsyncCodeModeContext(k)
        _clear_messages(k.stream)

        await ctx.apply_edit(NotebookEdit.delete_cells(1, 2))

        assert _graph_codes(k) == snapshot({"0": "a = 1", "2": "c = 3"})

        notifs = _notification_summary(k.stream)
        ids_notif = [n for n in notifs if n["op"] == "update-cell-ids"]
        assert ids_notif == snapshot(
            [{"op": "update-cell-ids", "cell_ids": ["0", "2"]}]
        )


class TestApplyEditReplace:
    async def test_replace_code(self, k: Kernel) -> None:
        await k.run([ExecuteCellCommand(cell_id="0", code="x = 1")])
        assert k.globals["x"] == 1

        ctx = AsyncCodeModeContext(k)
        _clear_messages(k.stream)

        await ctx.apply_edit(
            NotebookEdit.replace_cells(0, [NotebookCellData(code="x = 42")])
        )

        assert k.globals["x"] == 42
        assert _graph_codes(k) == snapshot({"0": "x = 42"})

        notifs = _notification_summary(k.stream)
        code_notifs = [n for n in notifs if n["op"] == "update-cell-codes"]
        assert code_notifs == snapshot(
            [
                {
                    "op": "update-cell-codes",
                    "cell_ids": ["0"],
                    "codes": ["x = 42"],
                    "stale": False,
                }
            ]
        )

    async def test_replace_config_only(self, k: Kernel) -> None:
        await k.run([ExecuteCellCommand(cell_id="0", code="x = 1")])

        ctx = AsyncCodeModeContext(k)
        _clear_messages(k.stream)

        await ctx.apply_edit(
            NotebookEdit.replace_cells(
                0, [NotebookCellData(config=CellConfig(hide_code=True))]
            )
        )

        assert k.globals["x"] == 1
        assert _graph_codes(k) == snapshot({"0": "x = 1"})

        notifs = _notification_summary(k.stream)
        code_notifs = [n for n in notifs if n["op"] == "update-cell-codes"]
        assert code_notifs == snapshot([])


class TestApplyEditCombined:
    async def test_delete_and_insert(self, k: Kernel) -> None:
        await k.run(
            [
                ExecuteCellCommand(cell_id="0", code="a = 1"),
                ExecuteCellCommand(cell_id="1", code="b = 2"),
                ExecuteCellCommand(cell_id="2", code="c = 3"),
            ]
        )

        ctx = AsyncCodeModeContext(k)
        _clear_messages(k.stream)

        await ctx.apply_edit(
            [
                NotebookEdit.delete_cells(1, 2),
                NotebookEdit.insert_cells(
                    1, [NotebookCellData(code="d = a + c")]
                ),
            ]
        )

        assert k.globals["d"] == 4
        codes = _graph_codes(k)
        assert "1" not in codes
