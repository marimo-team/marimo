# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any

import pytest

from marimo._ast.compiler import get_filename
from marimo._runtime.marimo_pdb import MarimoPdb
from marimo._runtime.runtime import Kernel
from marimo._types.ids import CellId_t
from tests.conftest import ExecReqProvider

if TYPE_CHECKING:
    from types import FrameType

CELL_ID = CellId_t("0")


async def test_pdb_patched(
    execution_kernel: Kernel, exec_req: ExecReqProvider
) -> None:
    k = execution_kernel
    await k.run([exec_req.get("import pdb")])

    pdb = k.globals["pdb"]
    assert pdb.Pdb == MarimoPdb
    assert k.debugger.stdout is k.stdout
    assert k.debugger.stdin is k.stdin


def _debugger_stopped_in(glbls: dict[str, Any], filename: str) -> MarimoPdb:
    """A debugger stopped in a module-level frame compiled as `filename`."""
    glbls["_marimo_test_capture"] = sys._getframe
    exec(
        compile(
            "_marimo_test_frame = _marimo_test_capture()", filename, "exec"
        ),
        glbls,
    )
    frame: FrameType = glbls.pop("_marimo_test_frame")
    del glbls["_marimo_test_capture"]

    debugger = MarimoPdb(readrc=False)
    debugger.reset()
    debugger.setup(frame, None)
    return debugger


def test_getval_resolves_cell_local() -> None:
    glbls: dict[str, Any] = {"a": 7, "_cell_0_b": 10}
    debugger = _debugger_stopped_in(glbls, get_filename(CELL_ID))

    # Regular globals keep working, and so do the cell's private names, which
    # are stored mangled but typed as the user wrote them.
    assert debugger._getval("a") == 7
    assert debugger._getval("_b") == 10
    assert debugger._getval("_b + a") == 17
    assert debugger._getval_except("_b") == 10


def test_getval_leaves_unknown_locals_alone() -> None:
    glbls: dict[str, Any] = {"_cell_0_b": 10}
    debugger = _debugger_stopped_in(glbls, get_filename(CELL_ID))

    with pytest.raises(NameError):
        debugger._getval("_nope")


def test_getval_prefers_unmangled_name() -> None:
    # Underscore-prefixed imports without an alias are deliberately left
    # unmangled; they must keep shadowing the cell-local of the same name.
    glbls: dict[str, Any] = {"_": "import", "_cell_0_": "cell local"}
    debugger = _debugger_stopped_in(glbls, get_filename(CELL_ID))

    assert debugger._getval("_") == "import"


def test_getval_ignores_non_cell_frames() -> None:
    glbls: dict[str, Any] = {"_cell_0_b": 10}
    debugger = _debugger_stopped_in(glbls, "not_a_marimo_cell.py")

    with pytest.raises(NameError):
        debugger._getval("_b")


def test_statement_assigns_to_cell_local() -> None:
    glbls: dict[str, Any] = {"_cell_0_b": 10}
    debugger = _debugger_stopped_in(glbls, get_filename(CELL_ID))

    debugger.default("_b = _b + 1")

    # The assignment lands on the mangled name, so the cell sees it too.
    assert glbls["_cell_0_b"] == 11
    assert "_b" not in glbls


def test_statement_defines_new_local_unmangled() -> None:
    # A name that doesn't exist under either spelling is left untouched, so
    # pdb reports the usual NameError instead of a mangled one.
    glbls: dict[str, Any] = {"_cell_0_b": 10}
    debugger = _debugger_stopped_in(glbls, get_filename(CELL_ID))

    debugger.default("_c = 1")

    assert glbls["_c"] == 1


def test_getval_keeps_names_bound_by_the_expression() -> None:
    # A lambda parameter or comprehension target belongs to the expression the
    # user just typed, not to the cell, so it must not be rewritten.
    glbls: dict[str, Any] = {"_cell_0_b": 10, "_cell_0_xs": [1, 2, 3]}
    debugger = _debugger_stopped_in(glbls, get_filename(CELL_ID))

    assert debugger._getval("(lambda _b: _b + 1)(5)") == 6
    assert debugger._getval("[_b * 2 for _b in [1, 2]]") == [2, 4]
    assert debugger._getval("{_b: _b for _b in [1]}") == {1: 1}
    assert debugger._getval("list(_b for _b in [4])") == [4]

    # Names the expression doesn't bind still resolve to the cell's.
    assert debugger._getval("(lambda _x: _x + _b)(1)") == 11
    assert debugger._getval("[_v + _b for _v in _xs]") == [11, 12, 13]
    assert debugger._getval("(lambda _b=_b: _b)()") == 10


def test_mangle_keeps_names_bound_by_a_nested_def() -> None:
    # Same rule for a `def`: its parameters and its own locals are the
    # function's, even when the cell happens to define the same names.
    glbls: dict[str, Any] = {"_cell_0_b": 10, "_cell_0_c": 20}
    debugger = _debugger_stopped_in(glbls, get_filename(CELL_ID))

    source = "def _f(_b):\n    _c = _b + 1\n    return _c"
    assert debugger._mangle_cell_locals(source) == source

    # A name the function doesn't bind is still the cell's.
    assert "_cell_0_c" in debugger._mangle_cell_locals(
        "def _f(_b):\n    return _b + _c"
    )
