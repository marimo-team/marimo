# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any

import pytest

from marimo._ast.app import App
from marimo._ast.errors import (
    CycleError,
    DeleteNonlocalError,
    MultipleDefinitionError,
    UnparsableError,
)


# don't complain for useless expressions (cell outputs)
# ruff: noqa: B018
class TestApp:
    @staticmethod
    def test_run() -> None:
        app = App()

        @app.cell
        def one() -> tuple[int]:
            x = 0
            x
            return (x,)

        @app.cell
        def two(x: int, z: int) -> tuple[int]:
            a = x + z
            a + 1
            return (a,)

        @app.cell
        def __(x: int) -> tuple[int, int]:
            y = x + 1
            z = y + 1
            return y, z

        cell_manager = app._cell_manager
        cell_names = tuple(cell_manager.names())
        assert cell_names[0] == "one"
        assert cell_names[1] == "two"
        assert cell_names[2] == "__"

        codes = tuple(cell_manager.codes())
        assert codes[0] == "x = 0\nx"
        assert codes[1] == "a = x + z\na + 1"
        assert codes[2] == "y = x + 1\nz = y + 1"

        outputs, defs = app.run()

        assert outputs[0] == defs["x"]
        assert outputs[1] == defs["a"] + 1
        assert outputs[2] is None

        assert defs["x"] == 0
        assert (defs["y"], defs["z"]) == (1, 2)
        assert defs["a"] == 2

    @staticmethod
    def test_cycle() -> None:
        app = App()

        @app.cell
        def one(y: int) -> tuple[int]:
            x = y
            return (x,)

        @app.cell
        def two(x: int) -> tuple[int]:
            y = x
            return (y,)

        with pytest.raises(CycleError):
            app.run()

    @staticmethod
    def test_cycle_missing_args_rets() -> None:
        app = App()

        @app.cell
        def one():
            x = y  # noqa: F841, F821

        @app.cell
        def two():
            y = x  # noqa: F841, F821

        with pytest.raises(CycleError):
            app.run()

    @staticmethod
    def test_multiple_definitions() -> None:
        app = App()

        @app.cell
        def one() -> tuple[int]:
            x = 0
            return (x,)

        @app.cell
        def two() -> tuple[int]:
            x = 0
            return (x,)

        with pytest.raises(MultipleDefinitionError):
            app.run()

    @staticmethod
    def test_multiple_definitions_missing_args_rets() -> None:
        app = App()

        @app.cell
        def one():
            x = 0  # noqa: F841

        @app.cell
        def two():
            x = 0  # noqa: F841

        with pytest.raises(MultipleDefinitionError):
            app.run()

    @staticmethod
    def test_delete_nonlocal_missing_args_rets() -> None:
        app = App()

        @app.cell
        def one():
            x = 0  # noqa: F841

        @app.cell
        def two():
            del x  # noqa: F841, F821

        with pytest.raises(DeleteNonlocalError):
            app.run()

    @staticmethod
    def test_unparsable_cell() -> None:
        app = App()

        @app.cell
        def one() -> tuple[int]:
            x = 0
            return (x,)

        app._unparsable_cell("_ _")
        app._unparsable_cell("_ _", name="foo")

        with pytest.raises(UnparsableError):
            app.run()

    @staticmethod
    def test_init_not_rewritten_as_local() -> None:
        app = App()

        @app.cell
        def _() -> tuple[int]:
            class _A:
                def __init__(self, x: int) -> None:
                    self.x = x

            y = _A(10).x
            return (y,)

        _, defs = app.run()  # type: ignore
        assert defs == {"y": 10}

    @staticmethod
    def test_ref_local_var_from_nested_scope() -> None:
        app = App()

        @app.cell
        def _() -> tuple[int]:
            _x = 10

            def _f() -> int:
                return _x

            y = _f()
            return (y,)

        _, defs = app.run()  # type: ignore
        assert defs == {"y": 10}

    @staticmethod
    def test_resolve_var_not_local_from_nested_scope() -> None:
        app = App()

        @app.cell
        def _() -> tuple[str]:
            _x = 10  # noqa: F841

            def _f() -> str:
                _x = "nested"
                return _x

            y = _f()
            return (y,)

        _, defs = app.run()  # type: ignore
        assert defs == {"y": "nested"}

    @staticmethod
    def test_resolve_make_local_with_global_keywd() -> None:
        app = App()

        @app.cell
        def _() -> tuple[str]:
            def _f() -> str:
                global _x
                _x = "nested"  # type: ignore
                return _x  # type: ignore

            y = _f()
            return (y,)

        @app.cell
        def _() -> None:
            _x  # type: ignore  # noqa: F821
            return

        with pytest.raises(NameError) as e:
            app.run()

        assert "'_x' is not defined" in str(e.value)

    @staticmethod
    def test_locals_dont_leak() -> None:
        app = App()

        @app.cell
        def _() -> None:
            _x = 0  # noqa: F841
            return

        @app.cell
        def _() -> None:
            _x  # type: ignore
            return

        with pytest.raises(NameError) as e:
            app.run()

        assert "'_x' is not defined" in str(e.value)

    @staticmethod
    def test_dunder_dunder_not_local() -> None:
        app = App()

        @app.cell
        def _() -> tuple[int]:
            __x__ = 0
            return (__x__,)

        @app.cell
        def _(__x__: int) -> None:
            assert __x__ == 0
            return

        app.run()

    @staticmethod
    def test_app_width_config() -> None:
        app = App(width="full")
        assert app._config.width == "full"

    @staticmethod
    def test_app_width_default() -> None:
        app = App()
        assert app._config.width == "normal"

    @staticmethod
    def test_app_config_extra_args_ignored() -> None:
        app = App(width="full", fake_config="foo")
        assert app._config.asdict() == {"width": "full", "layout_file": None}

    @staticmethod
    def test_cell_config() -> None:
        app = App()

        @app.cell(disabled=True)
        def _() -> tuple[int]:
            __x__ = 0
            return (__x__,)

        @app.cell(hide_code=True)
        def _(__x__: int) -> None:
            assert __x__ == 0
            return

        cell_manager = app._cell_manager
        configs = tuple(cell_manager.configs())
        assert configs[0].disabled
        assert configs[1].hide_code

    @staticmethod
    def test_conditional_definition() -> None:
        app = App()

        @app.cell
        def _() -> tuple[int]:
            if False:
                x = 0
            y = 1
            return (x, y)

        _, defs = app.run()

        # x should not be in the defs dictionary
        assert defs == {"y": 1}

    @staticmethod
    def test_empty_iteration_conditional_definition() -> None:
        app = App()

        @app.cell
        def _() -> tuple[int]:
            objects = iter([])
            for obj in objects:  # noqa: B007
                pass
            return (obj, objects)

        _, defs = app.run()

        # obj should not be in the defs dictionary
        assert "obj" not in defs

    @staticmethod
    def test_run_pickle() -> None:
        app = App()

        @app.cell
        def __() -> tuple[Any]:
            import pickle

            return (pickle,)

        @app.cell
        def __() -> tuple[Any]:
            def foo(): ...

            return (foo,)

        @app.cell
        def __(pickle, foo) -> tuple[Any]:
            out = pickle.dumps(foo)
            return (out,)

        _, defs = app.run()

        assert defs["out"] is not None

    @staticmethod
    def test_run_async() -> None:
        app = App()

        @app.cell
        async def __() -> tuple[Any, int]:
            import asyncio

            await asyncio.sleep(0.01)
            x = 0
            return (
                asyncio,
                x,
            )

        @app.cell
        def __(x: int) -> tuple[int]:
            y = x + 1
            return (y,)

        _, defs = app.run()

        assert defs["x"] == 0
        assert defs["y"] == 1
