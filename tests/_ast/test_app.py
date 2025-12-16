# Copyright 2024 Marimo. All rights reserved.

from __future__ import annotations
import os
import pathlib
import subprocess
import sys
import textwrap
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import click
import pytest

from marimo._ast.app import (
    App,
    AppEmbedResult,
    AppKernelRunnerRegistry,
    InternalApp,
)
from marimo._ast.app_config import _AppConfig
from marimo._ast.errors import (
    CycleError,
    IncompleteRefsError,
    MultipleDefinitionError,
    SetupRootError,
    UnparsableError,
)
from marimo._ast.load import load_app
from marimo._convert.converters import MarimoConvert
from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins.stateless.flex import vstack
from marimo._runtime.context.types import get_context
from marimo._runtime.requests import SetUIElementValueRequest
from marimo._schemas.serialization import (
    AppInstantiation,
    CellDef,
    NotebookSerializationV1,
)
from marimo._types.ids import CellId_t
from tests.conftest import ExecReqProvider

if TYPE_CHECKING:
    from marimo._runtime.runtime import Kernel


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
    def test_run_with_refs() -> None:
        """Test that app.run() can override variables with provided defs."""
        app = App()

        @app.cell
        def config() -> tuple[int, float]:
            batch_size = 32
            learning_rate = 0.01
            return batch_size, learning_rate

        @app.cell
        def process_data(batch_size: int, learning_rate: float) -> tuple[float]:
            result = batch_size * learning_rate
            return (result,)

        @app.cell
        def other_cell() -> tuple[str]:
            message = "independent"
            return (message,)

        # Test 1: Run with default values
        outputs, defs = app.run()
        assert defs["batch_size"] == 32
        assert defs["learning_rate"] == 0.01
        assert defs["result"] == 32 * 0.01
        assert defs["message"] == "independent"

        # Test 2: Run with overridden values
        outputs, defs = app.run(defs={"batch_size": 64, "learning_rate": 0.001})
        assert defs["batch_size"] == 64
        assert defs["learning_rate"] == 0.001
        assert defs["result"] == 64 * 0.001
        assert defs["message"] == "independent"  # unaffected cell still runs

        # Test 3: Partial override - this should fail with IncompleteRefsError
        # because we're only providing batch_size but the config cell defines both
        # batch_size and learning_rate
        with pytest.raises(IncompleteRefsError) as exc_info:
            app.run(defs={"batch_size": 128})
        assert "learning_rate" in str(exc_info.value)
        assert "Missing: ['learning_rate']" in str(exc_info.value)
        assert "Provided refs: ['batch_size']" in str(exc_info.value)

    @staticmethod
    def test_run_with_refs_multiple_cells() -> None:
        """Test defs override with multiple cells that define different variables."""
        app = App()

        @app.cell
        def cell_a() -> tuple[int]:
            x = 10
            return (x,)

        @app.cell
        def cell_b() -> tuple[int]:
            y = 20
            return (y,)

        @app.cell
        def cell_c(x: int, y: int) -> tuple[int]:
            z = x + y
            return (z,)

        # Test: Override both x and y - cells a and b should be pruned
        outputs, defs = app.run(defs={"x": 100, "y": 200})
        assert defs["x"] == 100
        assert defs["y"] == 200
        assert defs["z"] == 300

        # Test: Override only x - cell a is pruned, cell b still runs
        outputs, defs = app.run(defs={"x": 50})
        assert defs["x"] == 50
        assert defs["y"] == 20  # cell_b still ran
        assert defs["z"] == 70

    @staticmethod
    def test_run_with_refs_setup_cell_protection() -> None:
        """Test that overriding setup cell definitions raises IncompleteRefsError."""
        app = App()

        with app.setup:
            import os
            setup_var = "from_setup"

        @app.cell
        def use_setup(setup_var: str) -> tuple[str]:
            result = f"Used {setup_var}"
            return (result,)

        # Test: Can still override non-setup variables
        @app.cell
        def normal_cell() -> tuple[int]:
            normal_var = 42
            return (normal_var,)

        # Test: Trying to override setup cell variables should fail
        with pytest.raises(TypeError) as exc_info:
            app.run(defs={"setup_var": "overridden"})
        assert "override" in str(exc_info.value)

        outputs, defs = app.run(defs={"normal_var": 100})
        assert defs["normal_var"] == 100
        assert "setup_var" in defs  # setup still ran

    @staticmethod
    def test_setup() -> None:
        app = App()

        with app.setup:
            x = 0

        # Evaluate whether returning a value on setup run makes sense.
        # x

        @app.cell
        def two(z: int) -> tuple[int]:
            a = x + z
            a + 1
            return (a,)

        @app.cell
        def __() -> tuple[int, int]:
            y = x + 1
            z = y + 1
            return y, z

        cell_manager = app._cell_manager
        cell_names = tuple(cell_manager.names())
        assert cell_names[0] == "setup"
        assert cell_names[1] == "two"
        assert cell_names[2] == "__"

        codes = tuple(cell_manager.codes())
        assert codes[0] == "x = 0"
        assert codes[1] == "a = x + z\na + 1"
        assert codes[2] == "y = x + 1\nz = y + 1"

        outputs, defs = app.run()

        assert outputs[0] == defs["a"] + 1
        assert outputs[1] is None

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
        def one() -> None:
            x = y  # noqa: F841, F821

        @app.cell
        def two() -> None:
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
        def one() -> None:
            x = 0  # noqa: F841

        @app.cell
        def two() -> None:
            x = 0  # noqa: F841

        with pytest.raises(MultipleDefinitionError):
            app.run()

    @staticmethod
    def test_delete_nonlocal_ok() -> None:
        app = App()

        @app.cell
        def one() -> None:
            x = 0  # noqa: F841

        @app.cell
        def two() -> None:
            del x  # noqa: F841, F821

        # smoke test, no error raised
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

        with pytest.raises(UnparsableError) as e:
            app.run()
        e.match("_ _")

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
    def test_dunder_rewritten_as_local() -> None:
        app = App()

        @app.cell
        def _() -> None:
            __ = 1  # noqa: F841
            return

        @app.cell
        def _() -> None:
            __  # type: ignore
            return

        with pytest.raises(NameError) as e:
            app.run()

        assert "'__' is not defined" in str(e.value)

    @staticmethod
    def test_app_width_config() -> None:
        app = App(width="full")
        assert app._config.width == "full"

    @staticmethod
    def test_app_width_default() -> None:
        app = App()
        assert app._config.width == "compact"

    @staticmethod
    def test_app_config_extra_args_ignored() -> None:
        app = App(width="full", fake_config="foo")
        assert app._config.asdict() == {
            "app_title": None,
            "css_file": None,
            "html_head_file": None,
            "width": "full",
            "layout_file": None,
            "auto_download": [],
            "sql_output": "auto",
        }

    @staticmethod
    def test_cell_config() -> None:
        app = App()

        @app.cell(column=0, disabled=True)
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
        assert configs[0].column is not None
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
            def foo() -> None: ...

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

    @staticmethod
    def test_run_mo_stop() -> None:
        app = App()

        @app.cell
        def _() -> Any:
            import marimo as mo
            return (mo,)

        @app.cell
        def _(mo) -> tuple[int]:
            mo.stop(True)
            x = 0
            return (x,)

        @app.cell
        def _() -> tuple[int]:
            y = 1
            return (y,)

        _, defs = app.run()
        assert "x" not in defs
        assert defs["y"] == 1

    @staticmethod
    def test_run_mo_stop_descendant() -> None:
        app = App()

        @app.cell
        def _() -> Any:
            import marimo as mo
            return (mo,)

        @app.cell
        def _(mo) -> tuple[int]:
            mo.stop(True)
            x = 0
            return (x,)

        @app.cell
        def _(x) -> tuple[int]:
            y = 1
            x
            return

        _, defs = app.run()
        assert "x" not in defs
        assert "y" not in defs

    @staticmethod
    def test_run_mo_stop_descendant_multiple() -> None:
        app = App()

        @app.cell
        def _() -> Any:
            import marimo as mo
            return (mo,)

        @app.cell
        def _(mo) -> tuple[int]:
            mo.stop(True)
            x = 0
            return (x,)

        @app.cell
        def _(mo) -> tuple[int]:
            mo.stop(True)
            y = 0
            return (y,)


        @app.cell
        def _(x) -> tuple[int]:
            x
            a = 0
            return

        @app.cell
        def _(y) -> tuple[int]:
            y
            b = 0
            return


        _, defs = app.run()
        assert "x" not in defs
        assert "y" not in defs
        assert "a" not in defs
        assert "b" not in defs


    @staticmethod
    def test_run_mo_stop_async() -> None:
        app = App()

        @app.cell
        def _() -> Any:
            import marimo as mo
            return (mo,)

        @app.cell
        def _(mo) -> tuple[int]:
            mo.stop(True)
            x = 0
            return (x,)

        @app.cell
        async def _() -> tuple[int]:
            y = 1
            return (y,)

        _, defs = app.run()
        assert "x" not in defs
        assert defs["y"] == 1

    @staticmethod
    def test_run_mo_stop_descendant_async() -> None:
        app = App()

        @app.cell
        def _() -> Any:
            import marimo as mo
            return (mo,)

        @app.cell
        def _(mo) -> tuple[int]:
            mo.stop(True)
            x = 0
            return (x,)

        @app.cell
        async def _(x) -> tuple[int]:
            y = 1
            x
            return

        _, defs = app.run()
        assert "x" not in defs
        assert "y" not in defs


    @pytest.mark.skipif(
        condition=not DependencyManager.matplotlib.has(),
        reason="requires matplotlib",
    )
    def test_marimo_mpl_backend_not_used(self):
        app = App()

        @app.cell
        def __() -> tuple[str]:
            import matplotlib

            backend = matplotlib.get_backend()
            return (backend,)

        _, defs = app.run()

        assert defs["backend"] != "module://marimo._output.mpl"

    @pytest.mark.skipif(
        condition=not DependencyManager.matplotlib.has(),
        reason="requires matplotlib",
    )
    def test_app_run_matplotlib_figures_closed(self) -> None:
        from matplotlib.axes import Axes

        app = App()

        @app.cell
        def __() -> None:
            import matplotlib.pyplot as plt

            plt.plot([1, 2])
            plt.gca()

        @app.cell
        def __(plt: Any) -> None:
            plt.plot([1, 1])
            plt.gca()

        outputs, _ = app.run()
        assert isinstance(outputs[0], Axes)
        assert isinstance(outputs[1], Axes)
        assert outputs[0] != outputs[1]

    @staticmethod
    def test_app_config_auto_download():
        # Test default value
        config = _AppConfig()
        assert config.auto_download == []

        # Test setting auto_download
        config = _AppConfig(auto_download=["html", "markdown"])
        assert config.auto_download == ["html", "markdown"]

        # Test updating auto_download
        config.update({"auto_download": ["html"]})
        assert config.auto_download == ["html"]

        # Test setting empty list
        config.update({"auto_download": []})
        assert config.auto_download == []

        # Test from_untrusted_dict
        config = _AppConfig.from_untrusted_dict(
            {"auto_download": ["markdown"]}
        )
        assert config.auto_download == ["markdown"]

        # Test asdict
        config_dict = config.asdict()
        assert config_dict["auto_download"] == ["markdown"]

        # Test invalid values are allowed for forward compatibility
        config = _AppConfig(auto_download=["invalid"])
        assert config.auto_download == ["invalid"]

    def test_has_file_and_dirname(self) -> None:
        app = App()

        @app.cell
        def f():
            file = __file__

        @app.cell
        def g():
            import marimo as mo

            dirpath = mo.notebook_dir()

        _, glbls = app.run()
        assert glbls["file"] == __file__
        assert glbls["dirpath"] == pathlib.Path(glbls["file"]).parent

    def test_notebook_location(self) -> None:
        app = App()

        @app.cell
        def __():
            import marimo as mo

            dirpath = mo.notebook_dir()
            location = mo.notebook_location()

        _, glbls = app.run()
        dirpath = glbls["dirpath"]
        location = glbls["location"]
        assert dirpath is not None
        assert location is not None
        assert dirpath == location

    def test_app_clone(self) -> None:
        app = App()

        @app.cell
        def __():
            import marimo as mo

            dirpath = mo.notebook_dir()
            location = mo.notebook_location()

        # same codes and names, different cell_ids
        clone = app.clone()
        assert list(InternalApp(clone).cell_manager.codes()) == list(
            InternalApp(app).cell_manager.codes()
        )
        assert list(InternalApp(clone).cell_manager.names()) == list(
            InternalApp(app).cell_manager.names()
        )
        assert list(InternalApp(clone).cell_manager.cell_ids()) != list(
            InternalApp(app).cell_manager.cell_ids()
        )

    def test_to_py(self) -> None:
        """Test that InternalApp.to_py() returns the Python code representation."""
        app = App()

        @app.cell
        def cell_one():
            x = 1
            return (x,)

        @app.cell
        def cell_two(x):
            y = x + 1
            return (y,)

        internal_app = InternalApp(app)
        python_code = internal_app.to_py()

        # Verify it returns a string containing Python code
        assert isinstance(python_code, str)
        assert "import marimo" in python_code
        assert "app = marimo.App(" in python_code
        assert "x = 1" in python_code
        assert "y = x + 1" in python_code
        assert "cell_one" in python_code
        assert "cell_two" in python_code


class TestInvalidSetup:
    @staticmethod
    def test_initial_setup() -> None:
        app = App()
        app._unparsable_cell(";",
                             name="setup")

        assert app._cell_manager.has_cell("setup")
        assert app._cell_manager.cell_name("setup") == "setup"

    @staticmethod
    def test_not_initial_setup() -> None:
        app = App()
        app._unparsable_cell(";",
                             name="other")
        app._unparsable_cell(";",
                             name="setup")

        assert not app._cell_manager.has_cell("setup")

    @staticmethod
    def test_not_initial_setup_cell() -> None:
        app = App()
        @app.cell
        def _():
            def B() -> float:
                return 1.0
        app._unparsable_cell(";",
                             name="setup")
        assert not app._cell_manager.has_cell("setup")


def test_app_config() -> None:
    config = _AppConfig.from_untrusted_dict({"width": "full"})
    assert config.width == "full"
    assert config.layout_file is None
    assert config.asdict() == {
        "app_title": None,
        "css_file": None,
        "html_head_file": None,
        "width": "full",
        "layout_file": None,
        "auto_download": [],
        "sql_output": "auto",
    }


def test_app_config_extra_args_ignored() -> None:
    config = _AppConfig.from_untrusted_dict(
        {"width": "full", "fake_config": "foo"}
    )
    assert config.width == "full"
    assert config.layout_file is None
    assert config.asdict() == {
        "app_title": None,
        "css_file": None,
        "html_head_file": None,
        "width": "full",
        "layout_file": None,
        "auto_download": [],
        "sql_output": "auto",
    }


def test_cli_args(tmp_path: pathlib.Path) -> None:
    py_file = tmp_path / "cli_args_script.py"
    content = """
    import marimo
    app = marimo.App()

    @app.cell
    def __():
        import marimo as mo
        print(mo.cli_args())
        return mo,

    if __name__ == "__main__":
        app.run()
    """
    py_file.write_text(textwrap.dedent(content))
    p = subprocess.run(
        [sys.executable, str(py_file), "--foo", "value1", "--bar", "value2"],
        stdout=subprocess.PIPE,
    )
    assert p.returncode == 0
    output = p.stdout.decode()
    assert "foo" in output
    assert "value1" in output
    assert "bar" in output
    assert "value2" in output


class TestAppComposition:
    async def test_app_embed(self) -> None:
        app = App()

        @app.cell
        def __() -> None:
            x = 1
            "hello"

        @app.cell
        def __() -> None:
            "world"

        result = await app.embed()
        assert result.output.text == vstack(["hello", "world"]).text
        assert set(result.defs.keys()) == set(["x"])
        assert result.defs["x"] == 1

    async def test_app_embed_none_stripped(self) -> None:
        app = App()

        @app.cell
        def __() -> None:
            "hello"

        @app.cell
        def __() -> None:
            None

        @app.cell
        def __() -> None:
            "world"

        result = await app.embed()
        # None shouldn't show up in output
        assert result.output.text == vstack(["hello", "world"]).text
        assert not result.defs

    async def test_app_embed_with_defs(self) -> None:
        """Test embed() with defs parameter to override cell definitions."""
        app = App()

        @app.cell
        def __() -> tuple[int]:
            x = 10
            return (x,)

        @app.cell
        def __(x: int) -> tuple[int]:
            y = x * 2
            return (y,)

        @app.cell
        def __(y: int) -> None:
            f"Result: {y}"

        # Test without override
        result = await app.embed()
        assert result.defs["x"] == 10
        assert result.defs["y"] == 20
        assert "Result: 20" in result.output.text

        # Test with override - cell defining x should be pruned
        result = await app.embed(defs={"x": 100})
        assert result.defs["x"] == 100
        assert result.defs["y"] == 200
        assert "Result: 200" in result.output.text

    async def test_app_embed_with_defs_ui_element_not_allowed(self) -> None:
        app = App()

        @app.cell
        def __() -> tuple[int]:
            x = 10
            return (x,)

        import marimo as mo

        with pytest.raises(ValueError) as excinfo:
            await app.embed(defs={"x": mo.ui.slider(1, 10)})

        assert "Substituting UI Elements for variables is not allowed" in str(excinfo.value)

    async def test_app_embed_with_defs_multiple_vars(self) -> None:
        """Test embed() with defs overriding a cell that defines multiple variables."""
        app = App()

        @app.cell
        def __() -> tuple[int, int]:
            a = 5
            b = 10
            return a, b

        @app.cell
        def __(a: int, b: int) -> None:
            f"Sum: {a + b}"

        # Test without override
        result = await app.embed()
        assert result.defs["a"] == 5
        assert result.defs["b"] == 10
        assert "Sum: 15" in result.output.text

        # Test with override - must provide both a and b
        result = await app.embed(defs={"a": 100, "b": 200})
        assert result.defs["a"] == 100
        assert result.defs["b"] == 200
        assert "Sum: 300" in result.output.text

    async def test_app_embed_with_defs_incomplete_refs_error(self) -> None:
        """Test that embed() raises IncompleteRefsError for partial overrides."""
        from marimo._ast.errors import IncompleteRefsError

        app = App()

        @app.cell
        def __() -> tuple[int, int]:
            x = 1
            y = 2
            return x, y

        @app.cell
        def __(x: int, y: int) -> None:
            f"{x} + {y}"

        # Should raise error when only providing x but not y
        with pytest.raises(IncompleteRefsError) as exc_info:
            await app.embed(defs={"x": 100})

        assert "y" in str(exc_info.value)
        assert "Missing: ['y']" in str(exc_info.value)

    async def test_app_embed_with_defs_multiple_cells(self) -> None:
        """Test embed() with defs pruning multiple cells."""
        app = App()

        @app.cell
        def __() -> tuple[int]:
            a = 1
            return (a,)

        @app.cell
        def __() -> tuple[int]:
            b = 2
            return (b,)

        @app.cell
        def __(a: int, b: int) -> tuple[int]:
            c = a + b
            return (c,)

        @app.cell
        def __(c: int) -> None:
            f"Result: {c}"

        # Override both a and b - should prune first two cells
        result = await app.embed(defs={"a": 10, "b": 20})
        assert result.defs["a"] == 10
        assert result.defs["b"] == 20
        assert result.defs["c"] == 30
        assert "Result: 30" in result.output.text

    async def test_app_embed_with_defs_partial_pruning(self) -> None:
        """Test embed() with defs pruning only some cells."""
        app = App()

        @app.cell
        def __() -> tuple[int]:
            x = 5
            return (x,)

        @app.cell
        def __() -> tuple[int]:
            y = 10
            return (y,)

        @app.cell
        def __(x: int, y: int) -> None:
            f"x={x}, y={y}"

        # Override only x - should prune only first cell
        result = await app.embed(defs={"x": 100})
        assert result.defs["x"] == 100
        assert result.defs["y"] == 10  # y cell still ran
        assert "x=100, y=10" in result.output.text

    async def test_app_embed_with_defs_stale_outputs(self) -> None:
        """Test that embed() doesn't return stale cached outputs with different defs."""
        app = App()

        @app.cell
        def __() -> tuple[int]:
            x = 10
            return (x,)

        @app.cell
        def __(x: int) -> None:
            "x is small" if x == 10 else "x is large"

        # First call - no override
        result_initial = await app.embed()
        assert result_initial.defs["x"] == 10
        assert "x is small" in result_initial.output.text

        # Second call - with first override
        result_override = await app.embed(defs={"x": 100})
        assert result_override.defs["x"] == 100
        assert "x is large" in result_override.output.text
        assert "x is small" not in result_override.output.text

        # Third call - with second override
        result_override2 = await app.embed(defs={"x": 200})
        assert result_override2.defs["x"] == 200
        assert "x is large" in result_override2.output.text
        assert "x is small" not in result_override2.output.text

        # Check that initial result wasn't mutated by subsequent calls
        assert result_initial.defs["x"] == 10
        assert "x is small" in result_initial.output.text
        assert "x is large" not in result_initial.output.text

    async def test_app_embed_with_defs_stale_outputs_kernel(
        self, k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        """Test embed() with different defs through kernel (tests caching code path)."""
        await k.run(
            [
                exec_req.get(
                    """
                    from marimo import App

                    app = App()

                    @app.cell
                    def __() -> tuple[int]:
                        x = 10
                        return (x,)

                    @app.cell
                    def __(x: int) -> None:
                        "x is small" if x == 10 else "x is large"
                    """
                ),
                exec_req.get(
                    """
                    # First call - no override
                    result_initial = await app.embed()
                    """
                ),
                exec_req.get(
                    """
                    # Second call - with first override
                    result_override = await app.embed(defs={"x": 100})
                    """
                ),
                exec_req.get(
                    """
                    # Third call - with second override
                    result_override2 = await app.embed(defs={"x": 200})
                    """
                ),
            ]
        )
        assert not k.errors

        result_initial = k.globals["result_initial"]
        result_override = k.globals["result_override"]
        result_override2 = k.globals["result_override2"]

        # Check first result - output then defs
        assert "x is small" in result_initial.output.text
        assert result_initial.defs["x"] == 10

        # Check second result with first override - output then defs
        assert "x is large" in result_override.output.text
        assert "x is small" not in result_override.output.text
        assert result_override.defs["x"] == 100

        # Check third result with second override - output then defs
        assert "x is large" in result_override2.output.text
        assert "x is small" not in result_override2.output.text
        assert result_override2.defs["x"] == 200

        # Check that initial result wasn't mutated by subsequent calls
        assert "x is small" in result_initial.output.text
        assert "x is large" not in result_initial.output.text
        assert result_initial.defs["x"] == 10

    @pytest.mark.xfail(
        True, reason="Flaky in CI, can't repro locally", strict=False
    )
    async def test_app_comp_basic(
        self, k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        await k.run(
            [
                exec_req.get(
                    """
                    from app_data.ui_element_dropdown import app
                    token = [0]
                    """
                ),
                exec_req.get(
                    """
                    import random

                    token[0] += 1
                    result = await app.embed()
                    """
                ),
            ]
        )
        assert not k.errors

        # store the token value now, so we can make sure it changes later,
        # ie can make sure cell re-ran
        token = k.globals["token"]
        result = k.globals["result"]
        # dropdown has name d in app
        dropdown_element = result.defs["d"]
        assert dropdown_element.value == "first"

        html = result.output.text
        assert "value is first" in html
        assert "value is second" not in html
        assert token[0] == 1

        assert await k.set_ui_element_value(
            SetUIElementValueRequest.from_ids_and_values(
                [(dropdown_element._id, ["second"])]
            )
        )
        assert token[0] == 2

        # make sure ui element value updated
        assert dropdown_element.value == "second"
        # make sure cell referencing app re-ran
        result = k.globals["result"]
        html = result.output.text
        assert "value is first" not in html
        assert "value is second" in html

    @pytest.mark.xfail(
        True, reason="Flaky in CI, can't repro locally", strict=False
    )
    async def test_app_comp_multiple_ui_elements(
        self, k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        ctx = get_context()

        assert ctx.app_kernel_runner_registry.size == 0
        await k.run(
            [
                exec_req.get(
                    """
                    from app_data.calculator import app
                    """
                ),
                exec_req.get(
                    """
                    result = await app.embed()
                    """
                ),
            ]
        )
        assert not k.errors
        assert ctx.app_kernel_runner_registry.size == 1

        result = k.globals["result"]
        app = k.globals["app"]
        app_kernel_runner = app._get_kernel_runner()
        # two number inputs: x and y
        x = result.defs["x"]
        y = result.defs["y"]
        assert x.value == 1
        assert y.value == 1

        assert app_kernel_runner == app._get_kernel_runner()
        assert ctx.app_kernel_runner_registry.size == 1
        # testing that only descendants of the updated UI elements run,
        # and that the other UI element is not reset
        assert await k.set_ui_element_value(
            SetUIElementValueRequest.from_ids_and_values([(x._id, 2)])
        )

        assert app_kernel_runner == app._get_kernel_runner()
        assert ctx.app_kernel_runner_registry.size == 1
        assert x.value == 2
        assert y.value == 1

        assert await k.set_ui_element_value(
            SetUIElementValueRequest.from_ids_and_values([(y._id, 3)])
        )

        assert x.value == 2
        assert y.value == 3

    @staticmethod
    def test_app_not_changed() -> None:
        app = App()

        with pytest.raises(SetupRootError):
            with app.setup:
                app = 1



    @staticmethod
    def test_setup_not_exposed() -> None:
        app = App()

        with pytest.raises(SetupRootError):
            with app.setup:
                try:
                    x = app is not None
                except NameError:
                    x = False


    @staticmethod
    def test_setup_in_memory() -> None:
        app = App()

        with app.setup:
            x = 0

        assert x == 0
        _, defs = app.run()
        assert defs["x"] == 0
        assert "app" not in defs

    @staticmethod
    def test_setup_hide_code() -> None:
        setup_cell_id = CellId_t("setup")

        # Test property access (default behavior, hide_code=False)
        app1 = App()
        with app1.setup:
            x = 1

        setup_cell = app1._cell_manager._cell_data.get(setup_cell_id)
        assert setup_cell is not None
        assert setup_cell.config.hide_code is False

        # Test method call with default (hide_code=False)
        app2 = App()
        with app2.setup():
            x2 = 1

        setup_cell = app2._cell_manager._cell_data.get(setup_cell_id)
        assert setup_cell is not None
        assert setup_cell.config.hide_code is False

        # Test hide_code=True
        app3 = App()
        with app3.setup(hide_code=True):
            y = 2

        setup_cell = app3._cell_manager._cell_data.get(setup_cell_id)
        assert setup_cell is not None
        assert setup_cell.config.hide_code is True

        # Test explicit hide_code=False
        app4 = App()
        with app4.setup(hide_code=False):
            z = 3

        setup_cell = app4._cell_manager._cell_data.get(setup_cell_id)
        assert setup_cell is not None
        assert setup_cell.config.hide_code is False


    @staticmethod
    async def test_app_embed_preserves_file_path(
        app: App
    ) -> None:
        with app.setup:
            from tests._ast.app_data import notebook_filename

        @app.cell
        async def _():
            app = await notebook_filename.app.embed()
            cloned = await notebook_filename.app.clone().embed()
            filename = "notebook_filename.py"
            directory = "app_data"
            return (app, cloned, filename, directory)

        @app.cell
        def _(app: AppEmbedResult, filename: str, directory: str) -> None:
            assert app.defs.get("this_is_foo_file").endswith(filename)
            assert app.defs.get("this_is_foo_path").stem == directory

        @app.cell
        def _(cloned: AppEmbedResult, filename: str, directory: str) -> None:
            assert cloned.defs.get("this_is_foo_file").endswith(filename)
            assert cloned.defs.get("this_is_foo_path").stem == directory


    @staticmethod
    async def test_app_embed_in_kernel(
        k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        await k.run(
            [
                exec_req.get(
                    """
                    from tests._ast.app_data import notebook_filename
                    """
                ),
                exec_req.get(
                    """
                    app = await notebook_filename.app.embed()
                    cloned = await notebook_filename.app.clone().embed()
                    """
                ),
            ]
        )
        assert not k.errors
        filename = "notebook_filename.py"
        directory = "app_data"
        assert k.globals["app"].defs.get("this_is_foo_file").endswith(filename)
        assert k.globals["cloned"].defs.get("this_is_foo_file").endswith(filename)
        assert k.globals["app"].defs.get("this_is_foo_path").stem == directory
        assert k.globals["cloned"].defs.get("this_is_foo_path").stem == directory


    @staticmethod
    async def test_app_embed_same_cell_in_kernel(
        k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        await k.run(
            [
                exec_req.get(
                    """
                    from tests._ast.app_data import notebook_filename
                    app = await notebook_filename.app.embed()
                    app
                    """
                ),
            ]
        )
        assert "App.embed() cannot be called" in k.stderr.messages[0]

    @staticmethod
    async def test_app_embed_same_cell_in_kernel_direct(
        k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        await k.run(
            [
                exec_req.get(
                    """
                    from tests._ast.app_data.notebook_filename import app
                    await app.embed()
                    """
                ),
            ]
        )
        assert "App.embed() cannot be called" in k.stderr.messages[0]


class TestAppKernelRunnerRegistry:
    def test_get_runner(self, k: Kernel) -> None:
        # `k` fixture installs a context, needed for AppKernelRunner
        del k
        app = App()
        registry = AppKernelRunnerRegistry()
        # Calling with the same app yields the same runner
        assert registry.get_runner(app) == registry.get_runner(app)

        # Calling with different app objects yields different runners
        assert registry.get_runner(app) != registry.get_runner(other := App())

        registry.remove_runner(app)
        registry.remove_runner(other)
        assert not registry._runners
