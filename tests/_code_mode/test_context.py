# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import msgspec
import pytest
from inline_snapshot import snapshot

from marimo._code_mode._context import AsyncCodeModeContext
from marimo._messaging.notification import (
    UpdateCellCodesNotification,
    UpdateCellIdsNotification,
)
from marimo._runtime.commands import ExecuteCellCommand
from marimo._runtime.runtime import Kernel


def _code_notifs(k: Kernel) -> list[UpdateCellCodesNotification]:
    return [
        op
        for op in k.stream.operations
        if isinstance(op, UpdateCellCodesNotification)
    ]


def _ids_notifs(k: Kernel) -> list[UpdateCellIdsNotification]:
    return [
        op
        for op in k.stream.operations
        if isinstance(op, UpdateCellIdsNotification)
    ]


def _clear_messages(k: Kernel) -> None:
    k.stream.messages.clear()


def _graph_codes(k: Kernel) -> dict[str, str]:
    return {str(cid): cell.code for cid, cell in k.graph.cells.items()}


class TestAddCell:
    async def test_add_into_empty(self, k: Kernel) -> None:
        ctx = AsyncCodeModeContext(k)
        _clear_messages(k)

        async with ctx as nb:
            cid = nb.create_cell("x = 1")
            nb.run_cell(cid)

        assert len(k.graph.cells) == 1
        cell = list(k.graph.cells.values())[0]
        assert cell.code == "x = 1"
        assert k.globals["x"] == 1

        code_notifs = msgspec.to_builtins(_code_notifs(k))
        assert len(code_notifs) == 1
        assert code_notifs[0]["codes"] == ["x = 1"]
        assert code_notifs[0]["code_is_stale"] is False

        ids_notifs = msgspec.to_builtins(_ids_notifs(k))
        assert len(ids_notifs) == 1
        assert len(ids_notifs[0]["cell_ids"]) == 1

    async def test_add_appends_by_default(self, k: Kernel) -> None:
        await k.run(
            [
                ExecuteCellCommand(cell_id="0", code="a = 10"),
                ExecuteCellCommand(cell_id="1", code="b = 20"),
            ]
        )
        ctx = AsyncCodeModeContext(k)
        _clear_messages(k)

        async with ctx as nb:
            cid = nb.create_cell("c = a + b")
            nb.run_cell(cid)

        assert len(k.graph.cells) == 3
        assert k.globals["c"] == 30

        # New cell should be last in the ordering notification.
        ids_notifs = _ids_notifs(k)
        assert len(ids_notifs) == 1
        cell_ids = ids_notifs[0].cell_ids
        assert cell_ids[:2] == ["0", "1"]
        assert len(cell_ids) == 3

    async def test_add_with_after(self, k: Kernel) -> None:
        await k.run(
            [
                ExecuteCellCommand(cell_id="0", code="a = 10"),
                ExecuteCellCommand(cell_id="1", code="b = 20"),
            ]
        )
        ctx = AsyncCodeModeContext(k)
        _clear_messages(k)

        async with ctx as nb:
            nb.create_cell("c = a + b", after="0")

        ids_notifs = _ids_notifs(k)
        cell_ids = ids_notifs[0].cell_ids
        assert cell_ids[0] == "0"
        # New cell should be after "0", before "1".
        assert cell_ids[2] == "1"

    async def test_add_without_run_does_not_execute(self, k: Kernel) -> None:
        ctx = AsyncCodeModeContext(k)
        _clear_messages(k)

        async with ctx as nb:
            nb.create_cell("x = 999")

        assert len(k.graph.cells) == 1
        assert "x" not in k.globals

        code_notifs = msgspec.to_builtins(_code_notifs(k))
        assert len(code_notifs) == 1
        assert code_notifs[0]["codes"] == ["x = 999"]
        assert code_notifs[0]["code_is_stale"] is True

    async def test_add_returns_cell_id(self, k: Kernel) -> None:
        ctx = AsyncCodeModeContext(k)

        async with ctx as nb:
            cid = nb.create_cell("x = 1")
            assert isinstance(cid, str)
            assert len(cid) > 0

    async def test_add_chain_after(self, k: Kernel) -> None:
        """Can reference a just-added cell's ID in a subsequent add."""
        ctx = AsyncCodeModeContext(k)

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
                ExecuteCellCommand(cell_id="0", code="a = 1"),
                ExecuteCellCommand(cell_id="1", code="b = 2"),
                ExecuteCellCommand(cell_id="2", code="c = 3"),
            ]
        )
        assert len(k.graph.cells) == 3

        ctx = AsyncCodeModeContext(k)
        _clear_messages(k)

        async with ctx as nb:
            nb.delete_cell("1")

        assert _graph_codes(k) == snapshot({"0": "a = 1", "2": "c = 3"})

        assert msgspec.to_builtins(_ids_notifs(k)) == snapshot(
            [{"op": "update-cell-ids", "cell_ids": ["0", "2"]}]
        )

    async def test_delete_cleans_globals(self, k: Kernel) -> None:
        """Deleting a cell removes its defs from kernel globals."""
        await k.run(
            [
                ExecuteCellCommand(cell_id="0", code="a = 1"),
                ExecuteCellCommand(cell_id="1", code="b = 2"),
            ]
        )
        assert k.globals["a"] == 1
        assert k.globals["b"] == 2

        ctx = AsyncCodeModeContext(k)
        async with ctx as nb:
            nb.delete_cell("1")

        assert k.globals["a"] == 1
        assert "b" not in k.globals

    async def test_delete_multiple(self, k: Kernel) -> None:
        await k.run(
            [
                ExecuteCellCommand(cell_id="0", code="a = 1"),
                ExecuteCellCommand(cell_id="1", code="b = 2"),
                ExecuteCellCommand(cell_id="2", code="c = 3"),
            ]
        )
        ctx = AsyncCodeModeContext(k)
        _clear_messages(k)

        async with ctx as nb:
            nb.delete_cell("0")
            nb.delete_cell("2")

        assert _graph_codes(k) == snapshot({"1": "b = 2"})


class TestUpdateCell:
    async def test_update_code(self, k: Kernel) -> None:
        await k.run([ExecuteCellCommand(cell_id="0", code="x = 1")])
        assert k.globals["x"] == 1

        ctx = AsyncCodeModeContext(k)
        _clear_messages(k)

        async with ctx as nb:
            nb.edit_cell("0", code="x = 42")
            nb.run_cell("0")

        assert k.globals["x"] == 42
        assert _graph_codes(k) == snapshot({"0": "x = 42"})

        assert msgspec.to_builtins(_code_notifs(k)) == snapshot(
            [
                {
                    "op": "update-cell-codes",
                    "cell_ids": ["0"],
                    "codes": ["x = 42"],
                    "code_is_stale": False,
                    "names": [],
                    "configs": [
                        {
                            "column": None,
                            "disabled": False,
                            "hide_code": False,
                        }
                    ],
                }
            ]
        )

    async def test_update_cleans_stale_globals(self, k: Kernel) -> None:
        """Updating code removes old defs that are no longer defined."""
        await k.run([ExecuteCellCommand(cell_id="0", code="x = 1\ny = 2")])
        assert k.globals["x"] == 1
        assert k.globals["y"] == 2

        ctx = AsyncCodeModeContext(k)
        async with ctx as nb:
            nb.edit_cell("0", code="x = 42")
            nb.run_cell("0")

        assert k.globals["x"] == 42
        assert "y" not in k.globals

    async def test_update_preserves_config(self, k: Kernel) -> None:
        """Updating only code preserves the cell's existing config."""
        await k.run([ExecuteCellCommand(cell_id="0", code="x = 1")])

        # Set hide_code=True on the cell.
        ctx = AsyncCodeModeContext(k)
        async with ctx as nb:
            nb.edit_cell("0", hide_code=True)

        assert k.cell_metadata["0"].config.hide_code is True

        # Update code without touching config — hide_code should stick.
        ctx = AsyncCodeModeContext(k)
        async with ctx as nb:
            nb.edit_cell("0", code="x = 42")
            nb.run_cell("0")

        assert k.globals["x"] == 42
        assert k.cell_metadata["0"].config.hide_code is True

    async def test_update_config_only(self, k: Kernel) -> None:
        await k.run([ExecuteCellCommand(cell_id="0", code="x = 1")])

        ctx = AsyncCodeModeContext(k)
        _clear_messages(k)

        async with ctx as nb:
            nb.edit_cell("0", hide_code=True)

        assert k.globals["x"] == 1
        assert _graph_codes(k) == snapshot({"0": "x = 1"})
        assert msgspec.to_builtins(_code_notifs(k)) == snapshot(
            [
                {
                    "op": "update-cell-codes",
                    "cell_ids": ["0"],
                    "codes": ["x = 1"],
                    "code_is_stale": False,
                    "names": [],
                    "configs": [
                        {
                            "column": None,
                            "disabled": False,
                            "hide_code": True,
                        }
                    ],
                }
            ]
        )


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
                ExecuteCellCommand(cell_id="0", code="a = 1"),
                ExecuteCellCommand(cell_id="1", code="b = a + 1"),
            ]
        )
        assert k.globals["b"] == 2

        ctx = AsyncCodeModeContext(k)
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
        await k.run([ExecuteCellCommand(cell_id="0", code="x = 1")])
        ctx = AsyncCodeModeContext(k)
        _clear_messages(k)

        async with ctx as nb:  # noqa: B018
            pass

        assert _graph_codes(k) == snapshot({"0": "x = 1"})

    async def test_exception_discards_ops(self, k: Kernel) -> None:
        """If an exception occurs, queued ops are discarded."""
        await k.run([ExecuteCellCommand(cell_id="0", code="x = 1")])
        ctx = AsyncCodeModeContext(k)

        try:
            async with ctx as nb:
                nb.create_cell("y = 2")
                raise ValueError("oops")
        except ValueError:
            pass

        # The add should not have been applied.
        assert _graph_codes(k) == snapshot({"0": "x = 1"})
        assert len(k.graph.cells) == 1

    async def test_run_deleted_cell_raises(self, k: Kernel) -> None:
        """Calling run_cell on a cell queued for deletion raises."""
        await k.run([ExecuteCellCommand(cell_id="0", code="x = 1")])
        ctx = AsyncCodeModeContext(k)

        with pytest.raises(ValueError, match="queued for deletion"):
            async with ctx as nb:
                nb.delete_cell("0")
                nb.run_cell("0")


class TestSummary:
    async def test_create_prints_summary(
        self, k: Kernel, capsys: object
    ) -> None:
        ctx = AsyncCodeModeContext(k)

        async with ctx as nb:
            nb.create_cell("x = 1")

        captured = capsys.readouterr()  # type: ignore[attr-defined]
        assert "created cell" in captured.out

    async def test_edit_prints_summary(
        self, k: Kernel, capsys: object
    ) -> None:
        await k.run([ExecuteCellCommand(cell_id="0", code="x = 1")])
        ctx = AsyncCodeModeContext(k)

        async with ctx as nb:
            nb.edit_cell("0", code="x = 2")

        captured = capsys.readouterr()  # type: ignore[attr-defined]
        assert "edited code of cell" in captured.out

    async def test_delete_prints_summary(
        self, k: Kernel, capsys: object
    ) -> None:
        await k.run([ExecuteCellCommand(cell_id="0", code="x = 1")])
        ctx = AsyncCodeModeContext(k)

        async with ctx as nb:
            nb.delete_cell("0")

        captured = capsys.readouterr()  # type: ignore[attr-defined]
        assert "deleted cell" in captured.out

    async def test_noop_prints_nothing(
        self, k: Kernel, capsys: object
    ) -> None:
        ctx = AsyncCodeModeContext(k)

        async with ctx as nb:  # noqa: B018
            pass

        captured = capsys.readouterr()  # type: ignore[attr-defined]
        assert captured.out == ""

    async def test_batch_summary(
        self, k: Kernel, capsys: object
    ) -> None:
        """Full batch: create+run, edit+run, delete, create (staged), re-run."""
        await k.run(
            [
                ExecuteCellCommand(cell_id="0", code="a = 1"),
                ExecuteCellCommand(cell_id="1", code="b = 2"),
                ExecuteCellCommand(cell_id="2", code="c = 3"),
            ]
        )
        ctx = AsyncCodeModeContext(k)

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
created and ran cell 'new_cell'
created cell 'staged'
edited code of cell '0' and ran
re-ran cell '2'
""")


class TestResolveTarget:
    async def test_create_after_pending_add_by_name(self, k: Kernel) -> None:
        """Can reference a just-added cell by name in a subsequent add."""
        ctx = AsyncCodeModeContext(k)

        async with ctx as nb:
            cid1 = nb.create_cell("x = 1", name="first")
            cid2 = nb.create_cell("y = x + 1", after="first")
            nb.run_cell(cid1)
            nb.run_cell(cid2)

        assert k.globals["x"] == 1
        assert k.globals["y"] == 2

        # "first" should come before the second cell in ordering.
        ids_notifs = _ids_notifs(k)
        cell_ids = ids_notifs[0].cell_ids
        assert len(cell_ids) == 2

    async def test_create_after_renamed_cell(self, k: Kernel) -> None:
        """Can reference a cell by its new name after edit_cell renames it."""
        await k.run(
            [
                ExecuteCellCommand(cell_id="0", code="a = 1"),
                ExecuteCellCommand(cell_id="1", code="b = 2"),
            ]
        )
        ctx = AsyncCodeModeContext(k)
        _clear_messages(k)

        async with ctx as nb:
            nb.edit_cell("0", name="renamed")
            cid = nb.create_cell("c = a + b", after="renamed")
            nb.run_cell(cid)

        assert k.globals["c"] == 3

        # New cell should be after "0" (renamed), before "1".
        ids_notifs = _ids_notifs(k)
        cell_ids = ids_notifs[0].cell_ids
        assert cell_ids[0] == "0"
        assert cell_ids[2] == "1"


class TestInstallPackages:
    async def test_install_single(self, k: Kernel) -> None:
        ctx = AsyncCodeModeContext(k)
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
        ctx = AsyncCodeModeContext(k)
        pm = k.packages_callbacks.package_manager
        assert pm is not None

        with patch.object(
            pm, "install", new_callable=AsyncMock, return_value=True
        ) as mock_install:
            async with ctx:
                ctx.install_packages("pandas", "polars>=0.20", "numpy==1.26")

        # Each package should have been installed one-by-one.
        installed = {
            call.args[0]: call.kwargs["version"]
            for call in mock_install.call_args_list
        }
        assert installed["pandas"] == ""
        assert installed["polars>=0.20"] == ""
        assert installed["numpy==1.26"] == ""
