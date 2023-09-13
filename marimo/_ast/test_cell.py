# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

import pytest

from marimo._ast.app import App
from marimo._ast.cell import cell_factory, parse_cell


class TestParseCell:
    @staticmethod
    def test_parse_simple() -> None:
        code = "x = 0\nz = y"
        cell = parse_cell(code)
        assert cell.key == hash(code)
        assert cell.code == code
        assert cell.defs == set(["x", "z"])
        assert cell.refs == set(["y"])

    @staticmethod
    def test_local_variables() -> None:
        code = "_, y = f(x)\ndef _foo():\n  _bar = 0\nimport _secret_module"
        cell = parse_cell(code)
        assert cell.defs == {"y"}
        assert cell.refs == {"f", "x"}

    @staticmethod
    def test_dunder_dunder_excluded() -> None:
        code = "__ = 10; __name__ = 20"
        cell = parse_cell(code)
        assert cell.defs == {"__", "__name__"}
        assert cell.refs == set()

    @staticmethod
    def test_local_class() -> None:
        code = "class _A: pass"
        cell = parse_cell(code)
        assert cell.defs == set()
        assert cell.refs == set()

    @staticmethod
    def test_alias_underscored_name() -> None:
        code = "import _m as m"
        cell = parse_cell(code)
        assert cell.defs == {"m"}
        assert cell.refs == set()

    @staticmethod
    def test_ref_local_var() -> None:
        code = "x = _y"
        cell = parse_cell(code)
        assert cell.defs == {"x"}
        assert cell.refs == set()

        code = "def f(x= _y): pass"
        cell = parse_cell(code)
        assert cell.defs == {"f"}
        assert cell.refs == set()


class TestCellFactory:
    @staticmethod
    def test_missing_return() -> None:
        def f() -> None:
            x = 10  # noqa: F841

        with pytest.raises(ValueError) as e:
            cell_factory(f)

        assert "missing a return statement" in str(e.value)

    @staticmethod
    def test_not_tuple() -> None:
        def f() -> int:
            x = 10  # noqa: F841
            return x

        with pytest.raises(ValueError) as e:
            cell_factory(f)  # type: ignore[type-var]

        assert "must return a tuple" in str(e.value)

    @staticmethod
    def test_missing_some_defs() -> None:
        def f() -> tuple[int]:
            x = 10
            y = x  # noqa: F841
            return (x,)

        with pytest.raises(ValueError) as e:
            cell_factory(f)

        assert "must return a tuple of all its defs" in str(e.value)

    @staticmethod
    def test_missing_some_refs() -> None:
        z = 0

        app = App()

        @app.cell
        def f(y: int) -> tuple[int]:
            x = y + z
            return (x,)

        with pytest.raises(ValueError) as e:
            app._validate_args()

        assert "must take all its refs as args" in str(e.value)

    @staticmethod
    def test_extra_returns() -> None:
        def f() -> tuple[int]:
            return (1,)

        with pytest.raises(ValueError) as e:
            cell_factory(f)

        assert "shouldn't return anything" in str(e.value)

    @staticmethod
    def return_local_variable() -> None:
        def f() -> tuple[int]:
            _x = 0
            return (_x,)

        with pytest.raises(ValueError) as e:
            cell_factory(f)

        assert "Names starting with underscores should not be returned" in str(
            e.value
        )

    @staticmethod
    def local_variable_as_arg() -> None:
        def f(_x: int) -> None:
            return

        with pytest.raises(ValueError) as e:
            cell_factory(f)

        assert (
            "Names starting with underscores should not be taken as "
            "parameters" in str(e.value)
        )
