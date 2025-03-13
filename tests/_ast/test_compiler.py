# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from functools import partial

import pytest

from marimo._ast import compiler
from marimo._ast.app import CellManager
from marimo._ast.visitor import ImportData, VariableData
from marimo._dependencies.dependencies import DependencyManager

compile_cell = partial(compiler.compile_cell, cell_id="0")

HAS_DUCKDB = DependencyManager.duckdb.has()


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
        code = "__ = 10\n_, y = f(x)\ndef _foo():\n  _bar = 0\nimport _secret_module as module"  # noqa: E501
        cell = compile_cell(code)
        assert cell.defs == {"module", "y"}
        assert cell.refs == {"f", "x"}
        assert cell.imported_namespaces == {"_secret_module"}

    @staticmethod
    def test_dunder_dunder_excluded() -> None:
        code = "__name__ = 20"
        cell = compile_cell(code)
        assert cell.defs == {"__name__"}
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
        assert cell.imported_namespaces == {"_m"}

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
        assert not cell.imported_namespaces


class TestCompilerFlags:
    @staticmethod
    def test_top_level_await_ok() -> None:
        code = "await foo()"
        cell = compile_cell(code)
        assert cell.refs == {"foo"}


class TestImportWorkspace:
    @staticmethod
    def test_import() -> None:
        code = "from a.b.c import d; x = None"
        cell = compile_cell(code)
        # "d" is the imported name ...
        assert cell.defs == {"d", "x"}
        assert cell.refs == set()
        # but "a" is the module from which it was imported
        assert cell.imported_namespaces == {"a"}
        assert not cell.import_workspace.is_import_block

    @staticmethod
    def test_simple_import_statement() -> None:
        code = "import foo"
        cell = compile_cell(code)
        assert cell.defs == set(["foo"])
        assert cell.import_workspace.is_import_block
        assert not cell.import_workspace.imported_defs
        assert len(list(cell.imports)) == 1
        assert list(cell.imports)[0].definition == "foo"
        assert list(cell.imports)[0].imported_symbol is None
        assert list(cell.imports)[0].module == "foo"
        assert list(cell.imports)[0].namespace == "foo"
        assert list(cell.imports)[0].import_level is None

    @staticmethod
    def test_dotted_import_statement() -> None:
        code = "import foo.bar"
        cell = compile_cell(code)
        assert cell.defs == set(["foo"])
        assert cell.import_workspace.is_import_block
        assert not cell.import_workspace.imported_defs
        assert len(list(cell.imports)) == 1
        assert list(cell.imports)[0].definition == "foo"
        assert list(cell.imports)[0].imported_symbol is None
        assert list(cell.imports)[0].module == "foo.bar"
        assert list(cell.imports)[0].namespace == "foo"
        assert list(cell.imports)[0].import_level is None

    @staticmethod
    def test_from_import() -> None:
        code = "from foo.bar import baz"
        cell = compile_cell(code)
        assert cell.defs == set(["baz"])
        assert cell.import_workspace.is_import_block
        assert not cell.import_workspace.imported_defs
        assert len(list(cell.imports)) == 1
        assert list(cell.imports)[0].definition == "baz"
        assert list(cell.imports)[0].imported_symbol == "foo.bar.baz"
        assert list(cell.imports)[0].module == "foo.bar"
        assert list(cell.imports)[0].namespace == "foo"
        assert list(cell.imports)[0].import_level == 0

    @staticmethod
    def test_multiple_imports() -> None:
        code = "import foo; import foo.bar; from foo.bar import baz"
        cell = compile_cell(code)
        assert cell.defs == set(["foo", "baz"])
        assert cell.import_workspace.is_import_block
        assert not cell.import_workspace.imported_defs
        assert len(list(cell.imports)) == 3

        foo = ImportData(
            definition="foo",
            imported_symbol=None,
            module="foo",
            import_level=None,
        )
        foo_bar = ImportData(
            definition="foo",
            imported_symbol=None,
            module="foo.bar",
            import_level=None,
        )
        foo_bar_baz = ImportData(
            definition="baz",
            imported_symbol="foo.bar.baz",
            module="foo.bar",
            import_level=0,
        )
        assert foo in cell.imports
        assert foo_bar in cell.imports
        assert foo_bar_baz in cell.imports

    @staticmethod
    def test_mixed_statements_not_import_block() -> None:
        code = "import foo; foo.configure()"
        cell = compile_cell(code)
        assert not cell.import_workspace.is_import_block
        assert not cell.import_workspace.imported_defs

        code = "x = 0; import foo"
        cell = compile_cell(code)
        assert not cell.import_workspace.is_import_block
        assert not cell.import_workspace.imported_defs

    @staticmethod
    def test_single_carried_import() -> None:
        foo = ImportData(
            definition="foo",
            imported_symbol=None,
            module="foo",
            import_level=None,
        )
        foo_bar = ImportData(
            definition="foo",
            imported_symbol=None,
            module="foo.bar",
            import_level=None,
        )
        foo_bar_baz = ImportData(
            definition="baz",
            imported_symbol="foo.bar.baz",
            module="foo.bar",
            import_level=0,
        )

        code = "import foo; import foo.bar; from foo.bar import baz"
        cell = compile_cell(code, carried_imports=[foo])
        assert cell.defs == set(["foo", "baz"])
        assert cell.import_workspace.is_import_block
        assert cell.import_workspace.imported_defs == set(["foo"])

        assert len(list(cell.imports)) == 3
        assert foo in cell.imports
        assert foo_bar in cell.imports
        assert foo_bar_baz in cell.imports

    @staticmethod
    def test_multiple_carried_imports() -> None:
        foo = ImportData(
            definition="foo",
            imported_symbol=None,
            module="foo",
            import_level=None,
        )
        foo_bar = ImportData(
            definition="foo",
            imported_symbol=None,
            module="foo.bar",
            import_level=None,
        )
        foo_bar_baz = ImportData(
            definition="baz",
            imported_symbol="foo.bar.baz",
            module="foo.bar",
            import_level=0,
        )

        code = "import foo; import foo.bar; from foo.bar import baz"
        cell = compile_cell(code, carried_imports=[foo, foo_bar, foo_bar_baz])
        assert cell.defs == set(["foo", "baz"])
        assert cell.import_workspace.is_import_block
        assert cell.import_workspace.imported_defs == set(["foo", "baz"])

        assert len(list(cell.imports)) == 3
        assert foo in cell.imports
        assert foo_bar in cell.imports
        assert foo_bar_baz in cell.imports

    @staticmethod
    def test_carried_imports_mismatch() -> None:
        # import foo and import foo.bar both define "foo", but they are
        # different imports; as such, the import should not be carried over
        foo = ImportData(
            definition="foo",
            imported_symbol=None,
            module="foo",
            import_level=None,
        )
        code = "import foo.bar"
        cell = compile_cell(code, carried_imports=[foo])
        assert cell.defs == set(["foo"])
        assert cell.import_workspace.is_import_block
        assert not cell.import_workspace.imported_defs


@pytest.mark.skipif(not HAS_DUCKDB, reason="Missing DuckDB")
class TestParseSQLCell:
    @staticmethod
    def test_table_definition() -> None:
        code = 'mo.sql("CREATE TABLE t1 (i INTEGER, j INTEGER)")'
        cell = compile_cell(code)
        assert cell.key == hash(code)
        assert cell.code == code
        assert cell.defs == set(["t1"])
        assert cell.refs == set(["mo"])
        assert cell.language == "sql"
        assert cell.variable_data == {"t1": [VariableData("table")]}

    @staticmethod
    def test_table_reference() -> None:
        code = 'mo.sql("SELECT * from t1")'
        cell = compile_cell(code)
        assert cell.key == hash(code)
        assert cell.code == code
        assert not cell.defs
        assert cell.refs == set(["mo", "t1"])
        assert cell.language == "sql"
        assert not cell.variable_data

    @staticmethod
    @pytest.mark.parametrize(
        "code",
        [
            'duckdb.sql("CREATE TABLE t1 (i INTEGER, j INTEGER)")',
            'duckdb.execute("CREATE TABLE t1 (i INTEGER, j INTEGER)")',
        ],
    )
    def test_table_definition_duckdb(code: str) -> None:
        cell = compile_cell(code)
        assert cell.key == hash(code)
        assert cell.code == code
        assert cell.defs == set(["t1"])
        assert cell.refs == set(["duckdb"])
        assert cell.language == "sql"
        assert cell.variable_data == {"t1": [VariableData("table")]}

    @staticmethod
    @pytest.mark.parametrize(
        "code",
        [
            'duckdb.sql("SELECT * from t1")',
            'duckdb.execute("SELECT * from t1")',
        ],
    )
    def test_table_reference_duckdb(code: str) -> None:
        cell = compile_cell(code)
        assert cell.key == hash(code)
        assert cell.code == code
        assert not cell.defs
        assert cell.refs == set(["duckdb", "t1"])
        assert cell.language == "sql"
        assert not cell.variable_data


class TestCellFactory:
    @staticmethod
    def test_defs() -> None:
        """Defs inferred from function code, not returns"""

        def f() -> None:
            x = 10  # noqa: F841
            y = 20  # noqa: F841

        cell = compiler.cell_factory(f, cell_id="0")
        assert cell._cell.defs == {"x", "y"}
        assert not cell._cell.refs

    @staticmethod
    def test_refs() -> None:
        """Refs inferred from function code, not args"""

        def f() -> None:
            x = y  # noqa: F841 F821

        cell = compiler.cell_factory(f, cell_id="0")
        assert cell._cell.defs == {"x"}
        assert cell._cell.refs == {"y"}


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


class TestSemicolon:
    @staticmethod
    def test_return() -> None:
        # fmt: off
        def f() -> None:
            1  # noqa: B018
        # fmt: on

        cell = compiler.cell_factory(f, cell_id="0")
        assert eval(cell._cell.last_expr) == 1

    @staticmethod
    def test_return_suppressed() -> None:
        # fmt: off
        def f() -> None:
            1;  # noqa: B018 E703
        # fmt: on

        cell = compiler.cell_factory(f, cell_id="0")
        assert eval(cell._cell.last_expr) is None

    @staticmethod
    def test_return_last() -> None:
        # fmt: off
        def f() -> None:
            1; 2; 3  # noqa: B018 E702
        # fmt: on

        cell = compiler.cell_factory(f, cell_id="0")
        assert eval(cell._cell.last_expr) == 3

    @staticmethod
    def test_return_last_suppressed() -> None:
        # fmt: off
        def f() -> None:
            1; 2; 3;  # noqa: B018 E702 E703
        # fmt: on

        cell = compiler.cell_factory(f, cell_id="0")
        assert eval(cell._cell.last_expr) is None

    @staticmethod
    def test_return_comment() -> None:
        def f() -> None:
            1  # noqa: B018 # Has a comment;

        cell = compiler.cell_factory(f, cell_id="0")
        assert eval(cell._cell.last_expr) == 1

    @staticmethod
    def test_return_comment_suppressed() -> None:
        # fmt: off
        def f() -> None:
            1;  # noqa: B018 E703 # Has a comment
        # fmt: on

        cell = compiler.cell_factory(f, cell_id="0")
        assert eval(cell._cell.last_expr) is None

    @staticmethod
    def test_return_string_semicolon() -> None:
        def f() -> None:
            "#; splits on ;# are less than ideal"  # noqa: B018 Contains a ;#

        cell = compiler.cell_factory(f, cell_id="0")
        assert (
            eval(cell._cell.last_expr) == "#; splits on ;# are less than ideal"
        )

    @staticmethod
    def test_return_string_semicolon_suppressed() -> None:
        # fmt: off
        def f() -> None:
            "#; splits on ;# are less than ideal";  # noqa: B018 E703 Contains a ;#
        # fmt: on

        cell = compiler.cell_factory(f, cell_id="0")
        assert eval(cell._cell.last_expr) is None
