# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import logging
import os
import sys
from collections.abc import Awaitable
from pathlib import Path

import pytest

from marimo import _loggers, notebook_dir
from marimo._ast.app import App
from marimo._ast.cell import CellConfig
from marimo._runtime.context import runtime_context_installed
from marimo._runtime.context.filename import notebook_filename
from marimo._runtime.exceptions import MarimoRuntimeException


class TestCellRun:
    @staticmethod
    @pytest.mark.parametrize("relative", [False, True])
    def test_cell_location_after_chdir(
        tmp_path, monkeypatch, relative
    ) -> None:
        monkeypatch.chdir(tmp_path)
        directory = tmp_path / "notebooks with spaces"
        directory.mkdir()
        filename = directory / "notebook.py"
        app = App(
            _filename=str(
                filename.relative_to(tmp_path) if relative else filename
            )
        )

        @app.cell
        def location():
            import os

            import marimo as mo

            os.chdir("notebooks with spaces")
            paths = (__file__, mo.notebook_dir(), mo.notebook_location())
            return (paths,)

        _, defs = location.run()
        assert defs["paths"] == (str(filename), directory, directory)

    @staticmethod
    @pytest.mark.parametrize("fail", [False, True])
    def test_nested_cell_locations(tmp_path, fail) -> None:
        outer_dir = tmp_path / "outer"
        inner_dir = tmp_path / "inner"
        outer_dir.mkdir()
        inner_dir.mkdir()
        outer_app = App(_filename=str(outer_dir / "notebook.py"))
        inner_app = App(_filename=str(inner_dir / "notebook.py"))

        @inner_app.cell
        def inner(fail):
            import marimo as mo

            directory = mo.notebook_dir()
            if fail:
                raise ValueError("inner cell failed")
            return (directory,)

        @outer_app.cell
        def outer(fail, inner):
            import marimo as mo

            before = mo.notebook_dir()
            try:
                _, inner_defs = inner.run(fail=fail)
                inside = inner_defs["directory"]
            except ValueError:
                inside = None
            paths = (before, inside, mo.notebook_dir())
            return (paths,)

        _, defs = outer.run(fail=fail, inner=inner)
        assert defs["paths"] == (
            outer_dir,
            None if fail else inner_dir,
            outer_dir,
        )
        assert notebook_dir() == Path.cwd()

    @staticmethod
    async def test_concurrent_cell_locations(tmp_path) -> None:
        release = asyncio.Event()
        entered = [asyncio.Event(), asyncio.Event()]

        async def location(entered, release):
            import marimo as mo

            before = mo.notebook_dir()
            entered.set()
            await release.wait()
            paths = (before, mo.notebook_dir())
            return (paths,)

        directories = [tmp_path / "first", tmp_path / "second"]
        tasks = []
        for directory, ready in zip(directories, entered, strict=True):
            directory.mkdir()
            app = App(_filename=str(directory / "notebook.py"))
            cell = app.cell(location)
            tasks.append(
                asyncio.create_task(cell.run(entered=ready, release=release))
            )
        try:
            await asyncio.wait_for(
                asyncio.gather(*(event.wait() for event in entered)), timeout=5
            )
        finally:
            release.set()
        results = await asyncio.gather(*tasks)
        assert [defs["paths"] for _, defs in results] == [
            (directory, directory) for directory in directories
        ]

    @staticmethod
    async def test_cancelled_cell_restores_location(tmp_path) -> None:
        app = App()

        @app.cell
        async def location():
            import asyncio

            await asyncio.sleep(0)
            raise asyncio.CancelledError

        with notebook_filename(str(tmp_path / "outer.py")):
            with pytest.raises(asyncio.CancelledError):
                await location.run()
            assert notebook_dir() == tmp_path
        assert notebook_dir() == Path.cwd()

    @staticmethod
    @pytest.mark.parametrize("fail", [False, True])
    async def test_async_cell_notebook_location(fail: bool) -> None:
        app = App()
        main_module = sys.modules["__main__"]

        @app.cell
        async def location(fail):
            import asyncio

            import marimo as mo

            await asyncio.sleep(0)
            paths = (__file__, mo.notebook_dir(), mo.notebook_location())
            if fail:
                raise ValueError("cell failed")
            return (paths,)

        result = location.run(fail=fail)
        assert isinstance(result, Awaitable)
        if fail:
            with pytest.raises(MarimoRuntimeException) as exc_info:
                await result
            assert isinstance(exc_info.value.__cause__, ValueError)
        else:
            _, defs = await result
            assert defs["paths"] == (
                __file__,
                Path(__file__).parent,
                Path(__file__).parent,
            )
        assert not runtime_context_installed()
        assert sys.modules["__main__"] is main_module

    @staticmethod
    def test_cell_basic() -> None:
        def f() -> tuple[int]:
            x = 2 + 2
            "output"
            return (x,)

        app = App()
        cell = app.cell(f)
        assert cell.name == "f"
        assert not cell.refs
        assert cell.defs == {"x"}
        assert not cell._is_coroutine
        assert cell.run() == ("output", {"x": 4})

    @staticmethod
    async def test_async_cell_basic() -> None:
        async def f(asyncio) -> tuple[int]:
            await asyncio.sleep(0)

            x = 2 + 2
            "output"
            return (x,)

        app = App()
        cell = app.cell(f)
        assert cell.name == "f"
        assert cell.refs == {"asyncio"}
        assert cell.defs == {"x"}
        assert cell._is_coroutine

        import asyncio

        ret = cell.run(asyncio=asyncio)
        assert isinstance(ret, Awaitable)
        assert await ret == ("output", {"x": 4})

    @staticmethod
    def test_unknown_ref_raises() -> None:
        def f() -> None: ...

        app = App()
        cell = app.cell(f)
        with pytest.raises(ValueError) as einfo:
            cell.run(foo=1)
        assert "unexpected argument" in str(einfo.value)

    @staticmethod
    def test_substituted_ref_basic() -> None:
        app = App()

        @app.cell
        def g():
            x = 0
            y = 1
            return (x, y)

        @app.cell
        def h(x, y):
            z = x + y
            return (z,)

        assert h.run() == (None, {"z": 1})
        assert h.run(x=1) == (None, {"z": 2})
        assert h.run(y=0) == (None, {"z": 0})
        assert h.run(x=1, y=2) == (None, {"z": 3})

    @staticmethod
    def test_substituted_ref_chain() -> None:
        app = App()

        @app.cell
        def f():
            x = 0
            return (x,)

        @app.cell
        def g(x):
            y = x + 1
            return (y,)

        @app.cell
        def h(y):
            z = 2 * y
            return (z,)

        assert h.run() == (None, {"z": 2})
        assert h.run(y=0) == (None, {"z": 0})

        with pytest.raises(ValueError) as e:
            h.run(x=1)
        assert "unexpected argument" in str(e.value)

    @staticmethod
    def test_async_parent() -> None:
        app = App()

        @app.cell
        async def g(arg):
            await arg
            x = 0
            return (x,)

        @app.cell
        def h(x):
            y = x
            return (y,)

        assert g._is_coroutine
        # h is a coroutine because it depends on the execution of an async
        # function
        assert h._is_coroutine

    @staticmethod
    def test_async_chain() -> None:
        app = App()

        @app.cell
        async def f(arg):
            await arg
            x = 0
            return (x,)

        @app.cell
        def g(x):
            y = x
            return (y,)

        @app.cell
        def h(y):
            z = y
            return (z,)

        assert f._is_coroutine
        assert g._is_coroutine
        assert h._is_coroutine

    @staticmethod
    def test_empty_cell() -> None:
        app = App()

        @app.cell
        def f() -> None:
            return

        assert f.run() == (None, {})

    @staticmethod
    def test_conditional_def() -> None:
        app = App()

        @app.cell
        def f():
            if False:
                x = 0
            return (x,)

        # "x" was statically declared
        assert f.defs == {"x"}
        # "x" should not be in returns because it wasn't defined at runtime
        assert f.run() == (None, {})

    @staticmethod
    def test_import() -> None:
        from cell_data.named_cells import f, g, h

        assert f.name == "f"
        assert g.name == "g"
        assert h.name == "h"

        assert f.run() == (None, {"x": 0})
        assert g.run() == (None, {"y": 1})
        assert h.run() == (2, {"z": 2})

        assert g.run(x=1) == (None, {"y": 2})
        assert h.run(y=2) == (3, {"z": 3})

    @staticmethod
    def test_unhashable_import() -> None:
        from cell_data.named_cells import (
            unhashable_defined,
            unhashable_override_required,
        )

        assert unhashable_defined.name == "unhashable_defined"
        assert (
            unhashable_override_required.name == "unhashable_override_required"
        )

        assert unhashable_override_required.run(unhashable={0, 1}) == (
            {0, 1},
            {},
        )
        assert unhashable_defined.run() == (
            {0, 1, 2},
            {"unhashable": {0, 1, 2}},
        )

    @staticmethod
    def test_direct_call() -> None:
        from cell_data.named_cells import h, multiple, unhashable_defined

        assert h(1) == 2
        assert multiple() == (0, 1)
        assert unhashable_defined() == {0, 1, 2}

    @staticmethod
    def test_direct_call_with_global() -> None:
        old = os.environ.pop("PYTEST_CURRENT_TEST")
        old_version = os.environ.pop("PYTEST_VERSION")
        try:
            if "cell_data.named_cells" in sys.modules:
                del sys.modules["cell_data.named_cells"]
            from cell_data.named_cells import called_with_global

            # NB. depends on a variable `a` defined on module level.
            assert called_with_global(1) == 2
            assert called_with_global(x=1) == 2

            # Raise errors
            with pytest.raises(TypeError) as e:
                called_with_global(1, 1)

            with pytest.raises(TypeError) as e:
                called_with_global(x=1, a=1)
            assert "unexpected argument" in str(e.value)

            with pytest.raises(TypeError) as e:
                called_with_global(a=1)
            assert "unexpected argument" in str(e.value)

        finally:
            os.environ["PYTEST_CURRENT_TEST"] = old
            os.environ["PYTEST_VERSION"] = old_version

    @staticmethod
    def test_mismatch_args(app, caplog) -> None:
        # poor practice, but possible cell.
        @app.cell
        def basic(lots, of_, incorrect, args):  # noqa: ARG001
            1  # noqa: B018
            return

        assert basic.run() == (1, {})
        assert len(caplog.records) == 0
        with caplog.at_level(logging.WARNING):
            _loggers.marimo_logger().propagate = True
            assert basic() == 1
        assert len(caplog.records) == 1
        assert "signature" in caplog.text

    @staticmethod
    def test_direct_cyclic_call(app) -> None:
        # poor practice, but possible cell.
        @app.cell
        def cyclic():
            a = 1
            if False:
                a = b  # noqa: F821
            else:
                b = a
            b  # noqa: B018
            return

        assert cyclic.run() == (1, {"a": 1, "b": 1})
        assert cyclic() == 1


class TestReusableCell:
    @staticmethod
    def test_run_ok_with_setup_dep(app) -> None:
        with app.setup:
            z = 1

        @app.cell
        def _():
            y = 1
            return (y,)

        @app.cell
        def uses_setup(y):
            # non transitive
            x = y - z
            x  # noqa: B018
            return

        output, defs = uses_setup.run()
        assert output == 0
        assert defs == {"x": 0}

        output, defs = uses_setup.run(y=2)
        assert output == 1
        assert defs == {"x": 1}

        output, defs = uses_setup.run(z=2)
        assert output == -1
        assert defs == {"x": -1}

    @staticmethod
    def test_run_ok_with_setup_dep_rev_abc(app) -> None:
        # Arguments are alphabetized
        with app.setup:
            x = 1

        @app.cell
        def _():
            y = 1
            return (y,)

        @app.cell
        def uses_setup(y):
            z = y - x
            z  # noqa: B018
            return

        output, defs = uses_setup.run()
        assert output == 0
        assert defs == {"z": 0}, dict(defs)

        output, defs = uses_setup.run(y=2)
        assert output == 1
        assert defs == {"z": 1}

        output, defs = uses_setup.run(x=2)
        assert output == -1
        assert defs == {"z": -1}

    @staticmethod
    def test_run_setup_declares_more(app) -> None:
        # Arguments are alphabetized
        with app.setup:
            x = 1
            # a is important because it's an additional def that gets
            # inserted into the runtime
            a = 1

        @app.function
        def something_normally_scoped_for_a():
            return 1 + a

        @app.cell
        def _():
            y = 1
            return (y,)

        @app.cell
        def uses_setup(y):
            z = 0 * something_normally_scoped_for_a() + y - x
            z  # noqa: B018
            return

        output, defs = uses_setup.run()
        assert output == 0
        assert defs == {"z": 0}, dict(defs)

        output, defs = uses_setup.run(y=2)
        assert output == 1
        assert defs == {"z": 1}

        output, defs = uses_setup.run(x=2)
        assert output == -1
        assert defs == {"z": -1}


class TestDecoratedCells:
    @staticmethod
    def test_functool_wrapped(app) -> None:
        with app.setup:
            from functools import cache

        @app.function
        @cache
        def add(a: int, b: int) -> int:
            return a + b

        assert add(1, 2) == 3
        assert add.cache_info().hits == 0
        assert add(1, 2) == 3
        assert add.cache_info().hits == 1
        assert app._cell_manager.get_cell_data_by_name("add").cell.defs == {
            "add"
        }

    @staticmethod
    def test_cache_wrapped(app) -> None:
        with app.setup:
            from marimo import cache

        @app.function
        @cache
        def add(a: int, b: int) -> int:
            return a + b

        @app.cell
        def _() -> None:
            # Calling with the same app yields the same runner
            assert add(1, 2) == 3
            assert add.hits == 0

        # Calling with the same app yields the same runner
        assert add(1, 2) == 3
        assert add.hits == 0
        assert add(1, 2) == 3
        assert add.hits == 1
        assert app._cell_manager.get_cell_data_by_name("add").cell.defs == {
            "add"
        }

    @staticmethod
    def test_persistent_cache_wrapped(app) -> None:
        with app.setup:
            import shutil

            # Create a temporary cache directory
            import tempfile

            from marimo import persistent_cache as cache

            cache_dir = tempfile.mkdtemp()

        @app.function
        @cache(save_path=cache_dir)
        def add(a: int, b: int) -> int:
            return a + b

        @app.cell
        def _() -> None:
            # Calling with the same app yields the same runner
            assert add(1, 2) == 3
            # Because the cache is persistent
            assert add.hits == 1
            # Clean up the cache directory after the test
            shutil.rmtree(cache_dir)

        # Calling with the same app yields the same runner
        assert add(1, 2) == 3
        assert add.hits == 0
        assert add(1, 2) == 3
        assert add.hits == 1
        assert app._cell_manager.get_cell_data_by_name("add").cell.defs == {
            "add"
        }


def help_smoke() -> None:
    app = App()

    @app.cell
    async def f(x) -> None:
        await x
        return

    @app.cell
    def g() -> None:
        return

    assert "Async" in f._help().text
    assert "Async" not in g._help().text


def test_cell_config_asdict_without_defaults():
    config = CellConfig()
    assert config.asdict_without_defaults() == {}

    config = CellConfig(hide_code=True)
    assert config.asdict_without_defaults() == {"hide_code": True}

    config = CellConfig(hide_code=False)
    assert config.asdict_without_defaults() == {}


def test_is_different_from_default():
    config = CellConfig(hide_code=True)
    assert config.is_different_from_default()

    config = CellConfig(hide_code=False)
    assert not config.is_different_from_default()


def test_cell_config_configure_dict_is_partial():
    config = CellConfig(disabled=True, column=2)
    config.configure({"hide_code": True})
    assert config.hide_code is True
    assert config.disabled is True
    assert config.column == 2


def test_cell_config_configure_struct_writes_all_fields():
    config = CellConfig(disabled=True, column=2)
    config.configure(CellConfig(hide_code=True))
    assert config.hide_code is True
    assert config.disabled is False
    assert config.column is None
