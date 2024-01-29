# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from functools import partial

from marimo._ast import compiler
from marimo._ast.app import CellManager

compile_cell = partial(compiler.compile_cell, cell_id="0")


class TestParseCell:
    @staticmethod
    def test_parse_simple() -> None:
        code = "x = 0\nz = y"
        cell = compile_cell(code)
        assert cell.key == hash(code)
        assert cell.code == code
        assert cell.defs == set(["x", "z"])
        assert cell.refs == set(["y"])

    @staticmethod
    def test_local_variables() -> None:
        code = "_, y = f(x)\ndef _foo():\n  _bar = 0\nimport _secret_module as module"  # noqa: E501
        cell = compile_cell(code)
        assert cell.defs == {"module", "y"}
        assert cell.refs == {"f", "x"}
        assert cell.imported_modules == {"_secret_module"}

    @staticmethod
    def test_dunder_dunder_excluded() -> None:
        code = "__ = 10; __name__ = 20"
        cell = compile_cell(code)
        assert cell.defs == {"__", "__name__"}
        assert cell.refs == set()

    @staticmethod
    def test_local_class() -> None:
        code = "class _A: pass"
        cell = compile_cell(code)
        assert cell.defs == set()
        assert cell.refs == set()

    @staticmethod
    def test_alias_underscored_name() -> None:
        code = "import _m as m"
        cell = compile_cell(code)
        # m is the imported name ...
        assert cell.defs == {"m"}
        assert cell.refs == set()
        # but _m is the module from which it was imported
        assert cell.imported_modules == {"_m"}

    @staticmethod
    def test_ref_local_var() -> None:
        code = "x = _y"
        cell = compile_cell(code)
        assert cell.defs == {"x"}
        assert cell.refs == set()

        code = "def f(x= _y): pass"
        cell = compile_cell(code)
        assert cell.defs == {"f"}
        assert cell.refs == set()
        assert not cell.imported_modules

    @staticmethod
    def test_import() -> None:
        code = "from a.b.c import d; x = None"
        cell = compile_cell(code)
        # "d" is the imported name ...
        assert cell.defs == {"d", "x"}
        assert cell.refs == set()
        # but "a" is the module from which it was imported
        assert cell.imported_modules == {"a"}


class TestCellFactory:
    @staticmethod
    def test_defs() -> None:
        """defs inferred from function code, not returns"""

        def f() -> None:
            x = 10  # noqa: F841
            y = 20  # noqa: F841

        cf = compiler.cell_factory(f, cell_id="0")
        assert cf.cell.defs == {"x", "y"}
        assert not cf.cell.refs

    @staticmethod
    def test_refs() -> None:
        """refs inferred from function code, not args"""

        def f() -> None:
            x = y  # noqa: F841 F821

        cf = compiler.cell_factory(f, cell_id="0")
        assert cf.cell.defs == {"x"}
        assert cf.cell.refs == {"y"}


def test_cell_id_from_filename() -> None:
    cell_id = CellManager().create_cell_id()
    assert (
        compiler.cell_id_from_filename(compiler.get_filename(cell_id))
        == cell_id
    )
    assert (
        compiler.cell_id_from_filename(
            compiler.get_filename(cell_id, suffix="_abcd")
        )
        == cell_id
    )

    assert compiler.cell_id_from_filename("random_file.py") is None
