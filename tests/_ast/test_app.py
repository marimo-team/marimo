# Copyright 2024 Marimo. All rights reserved.

from __future__ import annotations

import pathlib
import subprocess
import textwrap
from typing import Any

import pytest
from marimo._ast.app import App, _AppConfig
from marimo._ast.errors import (
    CycleError,
    DeleteNonlocalError,
    MultipleDefinitionError,
    UnparsableError,
)
from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins.stateless.flex import vstack
from marimo._runtime.requests import SetUIElementValueRequest
from marimo._runtime.runtime import Kernel
from tests.conftest import ExecReqProvider


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
    def test_delete_nonlocal_missing_args_rets() -> None:
        app = App()

        @app.cell
        def one() -> None:
            x = 0  # noqa: F841

        @app.cell
        def two() -> None:
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
        ["python", str(py_file), "--foo", "value1", "--bar", "value2"],
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

    async def test_app_comp_basic(
        self, k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        await k.run(
            [
                exec_req.get(
                    """
                    from app_data.ui_element_dropdown import app
                    """
                ),
                exec_req.get(
                    """
                    import random

                    token = random.randint(0, 10000)
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

        await k.set_ui_element_value(
            SetUIElementValueRequest.from_ids_and_values(
                [(dropdown_element._id, ["second"])]
            )
        )
        assert token != k.globals["token"]

        # make sure ui element value updated
        assert dropdown_element.value == "second"
        # make sure cell referencing app re-ran
        result = k.globals["result"]
        html = result.output.text
        assert "value is first" not in html
        assert "value is second" in html

    async def test_app_comp_multiple_ui_elements(
        self, k: Kernel, exec_req: ExecReqProvider
    ) -> None:
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

        result = k.globals["result"]
        # two number inputs: x and y
        x = result.defs["x"]
        y = result.defs["y"]
        assert x.value == 1
        assert y.value == 1

        # testing that only descendants of the updated UI elements run,
        # and that the other UI element is not reset
        await k.set_ui_element_value(
            SetUIElementValueRequest.from_ids_and_values([(x._id, 2)])
        )
        assert x.value == 2
        assert y.value == 1

        await k.set_ui_element_value(
            SetUIElementValueRequest.from_ids_and_values([(y._id, 3)])
        )

        assert x.value == 2
        assert y.value == 3
