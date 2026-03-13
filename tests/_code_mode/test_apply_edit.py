# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from unittest.mock import AsyncMock, patch

from inline_snapshot import snapshot

from marimo._code_mode._context import AsyncCodeModeContext
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


class TestAddCell:
    async def test_add_into_empty(self, k: Kernel) -> None:
        ctx = AsyncCodeModeContext(k)
        _clear_messages(k.stream)

        async with ctx as nb:
            nb.add_cell("x = 1")

        assert len(k.graph.cells) == 1
        cell = list(k.graph.cells.values())[0]
        assert cell.code == "x = 1"
        assert k.globals["x"] == 1

        notifs = _notification_summary(k.stream)
        assert any(n["op"] == "update-cell-codes" for n in notifs)
        assert any(n["op"] == "update-cell-ids" for n in notifs)

    async def test_add_appends_by_default(self, k: Kernel) -> None:
        await k.run(
            [
                ExecuteCellCommand(cell_id="0", code="a = 10"),
                ExecuteCellCommand(cell_id="1", code="b = 20"),
            ]
        )
        ctx = AsyncCodeModeContext(k)
        _clear_messages(k.stream)

        async with ctx as nb:
            nb.add_cell("c = a + b")

        assert len(k.graph.cells) == 3
        assert k.globals["c"] == 30

        # New cell should be last in the ordering notification.
        notifs = _notification_summary(k.stream)
        ids_notif = [n for n in notifs if n["op"] == "update-cell-ids"]
        assert len(ids_notif) == 1
        cell_ids = ids_notif[0]["cell_ids"]
        assert cell_ids[0] == "0"
        assert cell_ids[1] == "1"
        # Third is the new cell (UUID, just check it's there).
        assert len(cell_ids) == 3

    async def test_add_with_after(self, k: Kernel) -> None:
        await k.run(
            [
                ExecuteCellCommand(cell_id="0", code="a = 10"),
                ExecuteCellCommand(cell_id="1", code="b = 20"),
            ]
        )
        ctx = AsyncCodeModeContext(k)
        _clear_messages(k.stream)

        async with ctx as nb:
            nb.add_cell("c = a + b", after="0")

        notifs = _notification_summary(k.stream)
        ids_notif = [n for n in notifs if n["op"] == "update-cell-ids"]
        cell_ids = ids_notif[0]["cell_ids"]
        assert cell_ids[0] == "0"
        # New cell should be after "0", before "1".
        assert cell_ids[2] == "1"

    async def test_add_draft_does_not_execute(self, k: Kernel) -> None:
        ctx = AsyncCodeModeContext(k)
        _clear_messages(k.stream)

        async with ctx as nb:
            nb.add_cell("x = 999", draft=True)

        assert len(k.graph.cells) == 1
        assert "x" not in k.globals

        notifs = _notification_summary(k.stream)
        code_notifs = [n for n in notifs if n["op"] == "update-cell-codes"]
        assert len(code_notifs) == 1
        assert code_notifs[0]["codes"] == ["x = 999"]
        assert code_notifs[0]["stale"] is True

    async def test_add_returns_cell_id(self, k: Kernel) -> None:
        ctx = AsyncCodeModeContext(k)

        async with ctx as nb:
            cid = nb.add_cell("x = 1")
            assert isinstance(cid, str)
            assert len(cid) > 0

    async def test_add_chain_after(self, k: Kernel) -> None:
        """Can reference a just-added cell's ID in a subsequent add."""
        ctx = AsyncCodeModeContext(k)

        async with ctx as nb:
            cid1 = nb.add_cell("x = 1")
            nb.add_cell("y = 2", after=cid1)

        assert k.globals["x"] == 1
        assert k.globals["y"] == 2


class TestDeleteCell:
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

        async with ctx as nb:
            nb.delete_cell("1")

        assert _graph_codes(k) == snapshot({"0": "a = 1", "2": "c = 3"})

        notifs = _notification_summary(k.stream)
        ids_notif = [n for n in notifs if n["op"] == "update-cell-ids"]
        assert ids_notif == snapshot(
            [{"op": "update-cell-ids", "cell_ids": ["0", "2"]}]
        )

    async def test_delete_multiple(self, k: Kernel) -> None:
        await k.run(
            [
                ExecuteCellCommand(cell_id="0", code="a = 1"),
                ExecuteCellCommand(cell_id="1", code="b = 2"),
                ExecuteCellCommand(cell_id="2", code="c = 3"),
            ]
        )
        ctx = AsyncCodeModeContext(k)
        _clear_messages(k.stream)

        async with ctx as nb:
            nb.delete_cell("0")
            nb.delete_cell("2")

        assert _graph_codes(k) == snapshot({"1": "b = 2"})


class TestUpdateCell:
    async def test_update_code(self, k: Kernel) -> None:
        await k.run([ExecuteCellCommand(cell_id="0", code="x = 1")])
        assert k.globals["x"] == 1

        ctx = AsyncCodeModeContext(k)
        _clear_messages(k.stream)

        async with ctx as nb:
            nb.update_cell("0", code="x = 42")

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

    async def test_update_config_only(self, k: Kernel) -> None:
        await k.run([ExecuteCellCommand(cell_id="0", code="x = 1")])

        ctx = AsyncCodeModeContext(k)
        _clear_messages(k.stream)

        async with ctx as nb:
            nb.update_cell("0", hide_code=True)

        assert k.globals["x"] == 1
        assert _graph_codes(k) == snapshot({"0": "x = 1"})

        notifs = _notification_summary(k.stream)
        code_notifs = [n for n in notifs if n["op"] == "update-cell-codes"]
        assert code_notifs == snapshot([])


class TestCombined:
    async def test_delete_and_add(self, k: Kernel) -> None:
        await k.run(
            [
                ExecuteCellCommand(cell_id="0", code="a = 1"),
                ExecuteCellCommand(cell_id="1", code="b = 2"),
                ExecuteCellCommand(cell_id="2", code="c = 3"),
            ]
        )

        ctx = AsyncCodeModeContext(k)
        _clear_messages(k.stream)

        async with ctx as nb:
            nb.delete_cell("1")
            nb.add_cell("d = a + c", after="0")

        assert k.globals["d"] == 4
        codes = _graph_codes(k)
        assert "1" not in codes

    async def test_noop_batch(self, k: Kernel) -> None:
        """An empty context manager does nothing."""
        await k.run([ExecuteCellCommand(cell_id="0", code="x = 1")])
        ctx = AsyncCodeModeContext(k)
        _clear_messages(k.stream)

        async with ctx as nb:  # noqa: B018
            pass

        assert _graph_codes(k) == snapshot({"0": "x = 1"})

    async def test_exception_discards_ops(self, k: Kernel) -> None:
        """If an exception occurs, queued ops are discarded."""
        await k.run([ExecuteCellCommand(cell_id="0", code="x = 1")])
        ctx = AsyncCodeModeContext(k)

        try:
            async with ctx as nb:
                nb.add_cell("y = 2")
                raise ValueError("oops")
        except ValueError:
            pass

        # The add should not have been applied.
        assert _graph_codes(k) == snapshot({"0": "x = 1"})
        assert len(k.graph.cells) == 1


class TestInstallPackages:
    async def test_install_single(self, k: Kernel) -> None:
        ctx = AsyncCodeModeContext(k)
        pm = k.packages_callbacks.package_manager
        assert pm is not None

        with patch.object(
            pm, "install", new_callable=AsyncMock, return_value=True
        ) as mock_install:
            await ctx.install_packages("pandas")

        assert mock_install.call_count == 1
        assert mock_install.call_args_list[0].args[0] == "pandas"
        assert mock_install.call_args_list[0].kwargs["version"] == ""

    async def test_install_multiple_with_specifiers(self, k: Kernel) -> None:
        ctx = AsyncCodeModeContext(k)
        pm = k.packages_callbacks.package_manager
        assert pm is not None

        with patch.object(
            pm, "install", new_callable=AsyncMock, return_value=True
        ) as mock_install:
            await ctx.install_packages("pandas", "polars>=0.20", "numpy==1.26")

        # Each package should have been passed through to install.
        installed = {
            call.args[0]: call.kwargs["version"]
            for call in mock_install.call_args_list
        }
        assert installed["pandas"] == ""
        assert installed["polars>=0.20"] == ""
        assert installed["numpy==1.26"] == ""
