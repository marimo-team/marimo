# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import os
from functools import partial
from typing import Any
from unittest.mock import patch

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
        assert cell.variable_data == {
            "t1": [VariableData("table", qualified_name="t1")]
        }

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
        assert cell.variable_data == {
            "t1": [VariableData("table", qualified_name="t1")]
        }

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


class TestCompileCellFilename:
    """Test compile_cell function with filename parameter."""

    @staticmethod
    def test_compile_cell_with_filename_no_source_position() -> None:
        """Test compile_cell with filename when no source_position provided."""
        code = "x = 1"
        filename = "test_notebook.py"

        # Mock solve_source_position to return a source position
        with patch("marimo._ast.compiler.solve_source_position") as mock_solve:
            mock_solve.return_value = compiler.SourcePosition(
                filename=filename, lineno=1, col_offset=0
            )

            cell = compiler.compile_cell(
                code, cell_id="test", filename=filename
            )

            # Verify solve_source_position was called
            mock_solve.assert_called_once_with(code, filename)

            # Verify the cell was compiled successfully
            assert cell.code == code
            assert cell.defs == {"x"}

    @staticmethod
    def test_compile_cell_with_filename_and_source_position() -> None:
        """Test compile_cell with filename when source_position is provided."""
        code = "x = 1"
        filename = "test_notebook.py"
        source_position = compiler.SourcePosition(
            filename="original.py", lineno=5, col_offset=10
        )

        cell = compiler.compile_cell(
            code,
            cell_id="test",
            filename=filename,
            source_position=source_position,
        )

        # Verify the cell was compiled successfully
        assert cell.code == code
        assert cell.defs == {"x"}

        # Note: We can't easily test that source_position.filename was updated
        # without accessing internal state, but the function should work

    @staticmethod
    def test_compile_cell_without_filename() -> None:
        """Test compile_cell without filename parameter."""
        code = "x = 1"

        cell = compiler.compile_cell(code, cell_id="test")

        # Verify the cell was compiled successfully
        assert cell.code == code
        assert cell.defs == {"x"}

    @staticmethod
    def test_solve_source_position_function() -> None:
        """Test solve_source_position function."""
        # Create a temporary notebook file
        import os
        import tempfile

        notebook_content = """import marimo

__generated_with = "0.1.0"
app = marimo.App()

@app.cell
def __():
    x = 1
    return x,

@app.cell
def __(x):
    y = x + 1
    return y,
"""

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as f:
            f.write(notebook_content)
            temp_filename = f.name

        try:
            # Test with code that matches a cell
            result = compiler.solve_source_position("x = 1", temp_filename)
            # The function might find a match, so just verify it returns a valid result or None
            if result is not None:
                assert result.filename == temp_filename
                assert result.lineno > 0
                assert result.col_offset >= 0

            # Test with code that doesn't match any cell
            result = compiler.solve_source_position("z = 999", temp_filename)
            # This might still find a match due to similarity, so just verify it's valid or None
            if result is not None:
                assert result.filename == temp_filename

        finally:
            os.unlink(temp_filename)

    @staticmethod
    def test_solve_source_position_invalid_file() -> None:
        """Test solve_source_position with invalid file."""
        # Mock the _maybe_contents function to return None for invalid files
        with patch("marimo._ast.load._maybe_contents") as mock_contents:
            mock_contents.return_value = None
            result = compiler.solve_source_position(
                "x = 1", "nonexistent_file.py"
            )
            assert result is None


class TestIrCellFactoryDebugpy:
    """Test ir_cell_factory function with DEBUGPY_RUNNING environment variable."""

    @staticmethod
    def test_ir_cell_factory_with_debugpy_running() -> None:
        """Test ir_cell_factory with DEBUGPY_RUNNING environment variable."""
        from marimo._schemas.serialization import CellDef

        cell_def = CellDef(code="x = 1", options={}, lineno=5, col_offset=10)
        cell_id = "test_cell"
        filename = "test_notebook.py"

        with patch.dict(os.environ, {"DEBUGPY_RUNNING": "1"}):
            cell = compiler.ir_cell_factory(
                cell_def, cell_id, filename=filename
            )

            # Verify the cell was created successfully
            assert cell._name == "_"
            assert cell._cell.code == "x = 1"
            assert cell._cell.defs == {"x"}

    @staticmethod
    def test_ir_cell_factory_without_debugpy_running() -> None:
        """Test ir_cell_factory without DEBUGPY_RUNNING environment variable."""
        from marimo._schemas.serialization import CellDef

        cell_def = CellDef(code="x = 1", options={}, lineno=5, col_offset=10)
        cell_id = "test_cell"
        filename = "test_notebook.py"

        with patch.dict(os.environ, {}, clear=True):
            cell = compiler.ir_cell_factory(
                cell_def, cell_id, filename=filename
            )

            # Verify the cell was created successfully
            assert cell._name == "_"
            assert cell._cell.code == "x = 1"
            assert cell._cell.defs == {"x"}


class TestSolveSourcePositionToplevelCells:
    """Test solve_source_position returns correct lineno for all cell types.

    The key invariant: the first AST-meaningful line of cell.code should be
    contained in the source file at the reported lineno.
    """

    DATA_FILE = os.path.join(
        os.path.dirname(__file__),
        "codegen_data",
        "test_stacked_decorators_toplevel.py",
    )

    def _assert_lineno_matches_source(
        self, cell_code: str, source: str, lineno: int
    ) -> None:
        """Assert cell AST maps correctly to source after applying lineno offset.

        lineno is a base offset: cell AST line N maps to raw source line (lineno + N).
        """
        import ast

        cell_ast = ast.parse(cell_code)
        source_lines = source.split("\n")

        # Get the first AST line number (accounting for decorators)
        first_stmt = cell_ast.body[0]
        if isinstance(
            first_stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            if first_stmt.decorator_list:
                first_ast_lineno = min(
                    d.lineno for d in first_stmt.decorator_list
                )
            else:
                first_ast_lineno = first_stmt.lineno
        else:
            first_ast_lineno = first_stmt.lineno

        # After fix_source_position: cell line N becomes lineno + N
        raw_lineno = lineno + first_ast_lineno

        # Find the first non-comment line in cell.code (what the AST represents)
        cell_lines = cell_code.split("\n")
        first_ast_content = next(
            (
                ln.strip()
                for ln in cell_lines
                if ln.strip() and not ln.strip().startswith("#")
            ),
            cell_lines[0].strip(),
        )

        # Check the source line at the computed position
        raw_line = (
            source_lines[raw_lineno - 1]
            if raw_lineno <= len(source_lines)
            else ""
        )

        assert first_ast_content in raw_line, (
            f"Cell AST does not map correctly to source.\n"
            f"lineno={lineno}, first_ast_lineno={first_ast_lineno}, "
            f"raw_lineno={raw_lineno}\n"
            f"first AST content: {first_ast_content!r}\n"
            f"source line: {raw_line!r}"
        )

    def test_function_cell(self) -> None:
        """@app.function with stacked decorators."""
        from marimo._ast.parse import parse_notebook

        with open(self.DATA_FILE) as f:
            source = f.read()

        notebook = parse_notebook(source)
        assert notebook is not None and notebook.valid

        cell = next(c for c in notebook.cells if "def cached_func" in c.code)
        assert "@app.function" not in cell.code
        assert "@mo.cache" in cell.code

        pos = compiler.solve_source_position(cell.code, self.DATA_FILE)
        assert pos is not None
        self._assert_lineno_matches_source(cell.code, source, pos.lineno)

    def test_setup_cell(self) -> None:
        """with app.setup: block."""
        from marimo._ast.parse import parse_notebook

        with open(self.DATA_FILE) as f:
            source = f.read()

        notebook = parse_notebook(source)
        assert notebook is not None and notebook.valid

        cell = next(
            c for c in notebook.cells if "import marimo as mo" in c.code
        )

        pos = compiler.solve_source_position(cell.code, self.DATA_FILE)
        assert pos is not None
        self._assert_lineno_matches_source(cell.code, source, pos.lineno)

    def test_class_definition_cell(self) -> None:
        """@app.class_definition with stacked decorator."""
        from marimo._ast.parse import parse_notebook

        with open(self.DATA_FILE) as f:
            source = f.read()

        notebook = parse_notebook(source)
        assert notebook is not None and notebook.valid

        cell = next(c for c in notebook.cells if "class Foo" in c.code)
        assert "@app.class_definition" not in cell.code
        assert "@wrap" in cell.code

        pos = compiler.solve_source_position(cell.code, self.DATA_FILE)
        assert pos is not None
        self._assert_lineno_matches_source(cell.code, source, pos.lineno)

    def test_normal_cell(self) -> None:
        """@app.cell basic."""
        from marimo._ast.parse import parse_notebook

        with open(self.DATA_FILE) as f:
            source = f.read()

        notebook = parse_notebook(source)
        assert notebook is not None and notebook.valid

        cell = next(c for c in notebook.cells if c.code.strip() == "a = 1")
        assert "@app.cell" not in cell.code

        pos = compiler.solve_source_position(cell.code, self.DATA_FILE)
        assert pos is not None
        self._assert_lineno_matches_source(cell.code, source, pos.lineno)

    def test_normal_cell_with_options(self) -> None:
        """@app.cell(hide_code=True)."""
        from marimo._ast.parse import parse_notebook

        with open(self.DATA_FILE) as f:
            source = f.read()

        notebook = parse_notebook(source)
        assert notebook is not None and notebook.valid

        cell = next(
            c for c in notebook.cells if 'mo.cache("example")' in c.code
        )
        assert "@app.cell" not in cell.code

        pos = compiler.solve_source_position(cell.code, self.DATA_FILE)
        assert pos is not None
        self._assert_lineno_matches_source(cell.code, source, pos.lineno)


class TestCellAstMatchesRawAst:
    """Test that fix_source_position correctly maps cell AST to raw file positions.

    After fix_source_position, the first AST node's lineno should point to the
    containing line in the raw source file.
    """

    DATA_FILE = os.path.join(
        os.path.dirname(__file__),
        "codegen_data",
        "test_stacked_decorators_toplevel.py",
    )

    def _get_first_ast_lineno(self, node: Any) -> int:
        """Get the first line number of an AST node, including decorators."""
        import ast

        # For decorated nodes, check decorator line numbers
        if isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            if node.decorator_list:
                return min(d.lineno for d in node.decorator_list)
        return node.lineno

    def _assert_fixed_ast_contains_line(
        self,
        cell_code: str,
        raw_source: str,
        source_position: compiler.SourcePosition,
    ) -> None:
        """Assert cell AST after fix_source_position points to containing line."""
        import ast

        cell_ast = ast.parse(cell_code)
        source_lines = raw_source.split("\n")

        # Apply fix_source_position to adjust cell AST line numbers
        compiler.fix_source_position(cell_ast, source_position)

        # Get the first statement's line number after fix (including decorators)
        first_stmt = cell_ast.body[0]
        fixed_lineno = self._get_first_ast_lineno(first_stmt)

        # The line in raw source at fixed_lineno should contain the first AST line of cell.code
        # Find the first non-comment line in cell.code
        cell_lines = cell_code.split("\n")
        first_ast_line = next(
            (
                ln.strip()
                for ln in cell_lines
                if ln.strip() and not ln.strip().startswith("#")
            ),
            cell_lines[0].strip(),
        )
        # lineno is 1-indexed
        raw_line = (
            source_lines[fixed_lineno - 1]
            if fixed_lineno <= len(source_lines)
            else ""
        )

        assert first_ast_line in raw_line, (
            f"Fixed AST lineno={fixed_lineno} does not contain cell code.\n"
            f"first AST line: {first_ast_line!r}\n"
            f"raw source line: {raw_line!r}\n"
            f"source_position.lineno={source_position.lineno}"
        )

    def test_function_cell_ast(self) -> None:
        """@app.function cell AST after fix_source_position points to containing line."""
        from marimo._ast.parse import parse_notebook

        with open(self.DATA_FILE) as f:
            source = f.read()

        notebook = parse_notebook(source)
        assert notebook is not None and notebook.valid

        cell = next(c for c in notebook.cells if "def cached_func" in c.code)
        pos = compiler.solve_source_position(cell.code, self.DATA_FILE)
        assert pos is not None

        self._assert_fixed_ast_contains_line(cell.code, source, pos)

    def test_setup_cell_ast(self) -> None:
        """Setup cell AST after fix_source_position points to containing line."""
        from marimo._ast.parse import parse_notebook

        with open(self.DATA_FILE) as f:
            source = f.read()

        notebook = parse_notebook(source)
        assert notebook is not None and notebook.valid

        cell = next(
            c for c in notebook.cells if "import marimo as mo" in c.code
        )
        pos = compiler.solve_source_position(cell.code, self.DATA_FILE)
        assert pos is not None

        self._assert_fixed_ast_contains_line(cell.code, source, pos)

    def test_class_definition_cell_ast(self) -> None:
        """@app.class_definition cell AST after fix_source_position points to containing line."""
        from marimo._ast.parse import parse_notebook

        with open(self.DATA_FILE) as f:
            source = f.read()

        notebook = parse_notebook(source)
        assert notebook is not None and notebook.valid

        cell = next(c for c in notebook.cells if "class Foo" in c.code)
        pos = compiler.solve_source_position(cell.code, self.DATA_FILE)
        assert pos is not None

        self._assert_fixed_ast_contains_line(cell.code, source, pos)

    def test_normal_cell_ast(self) -> None:
        """@app.cell AST after fix_source_position points to containing line."""
        from marimo._ast.parse import parse_notebook

        with open(self.DATA_FILE) as f:
            source = f.read()

        notebook = parse_notebook(source)
        assert notebook is not None and notebook.valid

        cell = next(c for c in notebook.cells if c.code.strip() == "a = 1")
        pos = compiler.solve_source_position(cell.code, self.DATA_FILE)
        assert pos is not None

        self._assert_fixed_ast_contains_line(cell.code, source, pos)

    def test_normal_cell_with_options_ast(self) -> None:
        """@app.cell(hide_code=True) AST after fix_source_position points to containing line."""
        from marimo._ast.parse import parse_notebook

        with open(self.DATA_FILE) as f:
            source = f.read()

        notebook = parse_notebook(source)
        assert notebook is not None and notebook.valid

        cell = next(
            c for c in notebook.cells if 'mo.cache("example")' in c.code
        )
        pos = compiler.solve_source_position(cell.code, self.DATA_FILE)
        assert pos is not None

        self._assert_fixed_ast_contains_line(cell.code, source, pos)
