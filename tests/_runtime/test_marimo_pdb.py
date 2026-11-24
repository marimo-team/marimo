from __future__ import annotations

import io
import sys
import warnings
from typing import Any

import pytest

from marimo._ast.compiler import compile_cell
from marimo._runtime.marimo_pdb import MarimoPdb
from marimo._runtime.runtime import Kernel
from marimo._types.ids import CellId_t
from tests.conftest import ExecReqProvider


async def test_pdb_patched(
    execution_kernel: Kernel, exec_req: ExecReqProvider
) -> None:
    k = execution_kernel
    await k.run([exec_req.get("import pdb")])

    pdb = k.globals["pdb"]
    assert pdb.Pdb == MarimoPdb
    assert k.debugger.stdout is k.stdout
    assert k.debugger.stdin is k.stdin


def _post_mortem(
    code: str, commands: list[str], cell_id: str = "0"
) -> tuple[str, dict[str, Any]]:
    """Run `code` as a cell that raises, then type `commands` at pdb."""
    cell = compile_cell(code, cell_id=CellId_t(cell_id))
    assert cell.body is not None
    assert cell.last_expr is not None
    glbls: dict[str, Any] = {}
    try:
        exec(cell.body, glbls)
        eval(cell.last_expr, glbls)
    except Exception as e:
        traceback = e.__traceback__
    stdout = io.StringIO()
    debugger = MarimoPdb(
        stdin=io.StringIO("\n".join([*commands, "q"]) + "\n"),  # type: ignore[arg-type]
        stdout=stdout,  # type: ignore[arg-type]
        readrc=False,
    )
    debugger.post_mortem(traceback)
    return stdout.getvalue(), glbls


def test_cell_locals_resolve_at_prompt() -> None:
    output, glbls = _post_mortem(
        'a = 7\n_b = 3 + a\n_b + "Hello"',
        [
            "p _b",
            "display _b",
            "_b * 2",
            "!_b = 100",
            "import math as _m; _c = _m.sqrt(_b)",
            "p _c",
        ],
    )
    assert output.split("(Pdb) ")[1:-1] == [
        "10\n",
        "display _b: 10\n",
        "20\n",
        "",
        "",
        "10.0\n",
    ]
    assert glbls["_cell_0_b"] == 100


def test_names_the_cell_does_not_mangle_are_untouched() -> None:
    output, _ = _post_mortem(
        "import _thread\na = 7\n_b = 1\n1 / 0",
        [
            "p _thread.__name__",
            "p [_b for _b in range(3)]",
            "p (lambda _b: _b * a)(2)",
        ],
    )
    assert output.split("(Pdb) ")[1:-1] == [
        "'_thread'\n",
        "[0, 1, 2]\n",
        "14\n",
    ]


def test_function_frame_resolves_cell_locals() -> None:
    output, _ = _post_mortem(
        "_b = 2\ndef f():\n    _x = 5\n    1 / 0\nf()",
        ["p _x", "!_x = 6", "p _x", "p _b", "!_y = _b + _x", "p _y"],
    )
    assert output.split("(Pdb) ")[1:-1] == ["5\n", "", "6\n", "2\n", "", "8\n"]


def test_unmangleable_cell_id_input_is_untouched() -> None:
    # Cell ids in an embedded app contain `-`, so their mangled names are
    # not identifiers and input runs as typed.
    output, _ = _post_mortem("_b = 1\n1 / 0", ["p _b"], cell_id="9f1c-Hbol")
    assert output.split("(Pdb) ")[1:-1] == [
        "*** NameError: name '_b' is not defined\n"
    ]


def test_mangled_names_typed_at_prompt_are_untouched() -> None:
    # `locals()` returns the compiled name, so a user can type it directly.
    output, glbls = _post_mortem(
        "_b = 1\n1 / 0",
        ["!_cell_0_b = 2", "!_cell_0_b += 1", "p _cell_0_b, _b"],
    )
    assert output.split("(Pdb) ")[1:-1] == ["", "", "(3, 3)\n"]
    assert glbls["_cell_0_b"] == 3
    assert "_cell_0_cell_0_b" not in glbls


def test_resolving_names_emits_no_syntax_warning() -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        output, _ = _post_mortem("_b = 1\n1 / 0", [r'p _b, "\d"'])
    assert output.split("(Pdb) ")[1:-1] == ["(1, '\\\\d')\n"]
    assert [w for w in caught if w.category is SyntaxWarning] == []


def test_errors_report_names_as_typed() -> None:
    output, _ = _post_mortem(
        "def _f(): pass\n1 / 0", ["enable 9999", "p _f(1)"]
    )
    assert output.split("(Pdb) ")[1:-1] == [
        "*** Breakpoint number 9999 out of range\n",
        "*** TypeError: _f() takes 0 positional arguments but 1 was given\n",
    ]


def test_unmangled_import_is_assigned_in_place() -> None:
    # An unaliased underscore import is not mangled in the cell, so an
    # assignment at the prompt must write to the same name.
    output, glbls = _post_mortem(
        "from re import _MAXCACHE\n1 / 0",
        ["!_MAXCACHE = 1", "!_MAXCACHE += 1", "p _MAXCACHE"],
    )
    assert output.split("(Pdb) ")[1:-1] == ["", "", "2\n"]
    assert glbls["_MAXCACHE"] == 2


@pytest.mark.skipif(
    sys.version_info < (3, 12), reason="comprehensions are inlined from 3.12"
)
def test_inlined_comprehension_local_shadows_cell_local() -> None:
    # The comprehension is inlined into the cell's frame, so its `_x` is
    # bound there without mangling.
    stdout = io.StringIO()
    debugger = MarimoPdb(
        stdin=io.StringIO("p _x\nc\n"),  # type: ignore[arg-type]
        stdout=stdout,  # type: ignore[arg-type]
        readrc=False,
    )
    cell = compile_cell(
        "_x = 10\n[stop()\n for _x in [20]]", cell_id=CellId_t("0")
    )
    assert cell.body is not None
    assert cell.last_expr is not None
    glbls: dict[str, Any] = {
        "stop": lambda: debugger.set_trace(sys._getframe(1))
    }
    exec(cell.body, glbls)
    eval(cell.last_expr, glbls)
    assert stdout.getvalue().split("(Pdb) ")[1:-1] == ["20\n"]
