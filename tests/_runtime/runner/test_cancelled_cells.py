# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import pytest

from marimo._runtime.runner.hook_context import CancelledCells
from marimo._types.ids import CellId_t


class TestCancelledCells:
    def test_empty(self) -> None:
        cc = CancelledCells()
        assert not cc
        assert CellId_t("a") not in cc
        assert list(cc) == []

    def test_add_and_contains(self) -> None:
        cc = CancelledCells()
        cc.add(
            CellId_t("raiser"),
            {CellId_t("child1"), CellId_t("child2")},
        )
        assert cc
        assert CellId_t("child1") in cc
        assert CellId_t("child2") in cc
        assert CellId_t("other") not in cc

    def test_contains_checks_descendants_not_raisers(self) -> None:
        """The `in` operator checks the flat descendant set, not just raisers."""
        cc = CancelledCells()
        cc.add(CellId_t("raiser"), {CellId_t("raiser"), CellId_t("child")})
        # Both raiser and descendant should be found
        assert CellId_t("raiser") in cc
        assert CellId_t("child") in cc

    def test_iter_yields_raising_cells(self) -> None:
        cc = CancelledCells()
        cc.add(CellId_t("r1"), {CellId_t("a")})
        cc.add(CellId_t("r2"), {CellId_t("b")})
        assert set(cc) == {CellId_t("r1"), CellId_t("r2")}

    def test_getitem(self) -> None:
        cc = CancelledCells()
        descendants = {CellId_t("x"), CellId_t("y")}
        cc.add(CellId_t("r"), descendants)
        assert cc[CellId_t("r")] == descendants

    def test_getitem_missing_raises(self) -> None:
        cc = CancelledCells()
        with pytest.raises(KeyError):
            cc[CellId_t("missing")]

    def test_multiple_raisers_flat_set_merges(self) -> None:
        """Flat set is the union of all descendants across raisers."""
        cc = CancelledCells()
        cc.add(CellId_t("r1"), {CellId_t("a"), CellId_t("b")})
        cc.add(CellId_t("r2"), {CellId_t("b"), CellId_t("c")})
        assert CellId_t("a") in cc
        assert CellId_t("b") in cc
        assert CellId_t("c") in cc
        assert CellId_t("d") not in cc

    def test_same_raiser_accumulates_descendants(self) -> None:
        """add() for the same raising cell unions, not overwrites, descendants."""
        cc = CancelledCells()

        cc.add(CellId_t("r"), {CellId_t("a")})
        cc.add(CellId_t("r"), {CellId_t("b")})

        assert CellId_t("a") in cc
        assert CellId_t("b") in cc
        assert cc[CellId_t("r")] == {CellId_t("a"), CellId_t("b")}

    def test_shared_reference_semantics(self) -> None:
        """Mutations after passing to a frozen dataclass are visible."""
        cc = CancelledCells()
        # Simulate: PostExecutionHookContext holds a reference,
        # then Runner.cancel() adds entries after construction.
        assert CellId_t("x") not in cc
        cc.add(CellId_t("r"), {CellId_t("x")})
        assert CellId_t("x") in cc

    def test_discard_descendant(self) -> None:
        """Discarding a descendant removes only it; siblings stay cancelled."""
        cc = CancelledCells()
        cc.add(CellId_t("r"), {CellId_t("d1"), CellId_t("d2")})
        cc.discard(CellId_t("d1"))
        assert CellId_t("d1") not in cc
        assert CellId_t("d2") in cc
        assert cc[CellId_t("r")] == {CellId_t("d2")}

    def test_discard_raising_cell_clears_its_descendants(self) -> None:
        """Discarding a raising cell drops its entry and the flat view with it.

        Regression: popping the raiser must not strand its descendants in the
        flat set, since nothing references them anymore.
        """
        cc = CancelledCells()
        cc.add(CellId_t("r"), {CellId_t("d1"), CellId_t("d2")})
        cc.discard(CellId_t("r"))
        assert CellId_t("r") not in cc
        assert CellId_t("d1") not in cc
        assert CellId_t("d2") not in cc
        assert not cc
        assert list(cc) == []

    def test_discard_last_descendant_prunes_empty_raiser(self) -> None:
        """A raiser with no cancelled descendants left is dropped entirely, so
        `bool()` and iteration don't report a phantom cancellation."""
        cc = CancelledCells()
        cc.add(CellId_t("r"), {CellId_t("d")})
        cc.discard(CellId_t("d"))
        assert CellId_t("d") not in cc
        assert not cc
        assert list(cc) == []

    def test_discard_shared_descendant_kept_by_other_raiser(self) -> None:
        """A descendant cancelled by two raisers survives discarding one raiser."""
        cc = CancelledCells()
        cc.add(CellId_t("a"), {CellId_t("b")})
        cc.add(CellId_t("x"), {CellId_t("b")})
        cc.discard(CellId_t("a"))
        # b is still cancelled by x.
        assert CellId_t("b") in cc
        assert set(cc) == {CellId_t("x")}

    def test_discard_cell_that_is_both_raiser_and_descendant(self) -> None:
        """A cell cancelled as a descendant that also raised its own cascade:
        discarding it clears it and the cells it raised, but leaves siblings."""
        cc = CancelledCells()
        # A cancelled {B, C}; B in turn cancelled D.
        cc.add(CellId_t("a"), {CellId_t("b"), CellId_t("c")})
        cc.add(CellId_t("b"), {CellId_t("d")})
        cc.discard(CellId_t("b"))
        assert CellId_t("b") not in cc
        assert CellId_t("d") not in cc
        # C was A's other descendant and is untouched.
        assert CellId_t("c") in cc
        assert set(cc) == {CellId_t("a")}
        assert cc[CellId_t("a")] == {CellId_t("c")}
