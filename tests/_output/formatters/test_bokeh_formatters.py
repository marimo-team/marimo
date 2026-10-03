from __future__ import annotations

import subprocess
import sys
from textwrap import dedent

import pytest

from marimo._dependencies.dependencies import DependencyManager

pytestmark = pytest.mark.skipif(
    not DependencyManager.bokeh.has(), reason="Bokeh not installed"
)


def run_in_subprocess(code: str) -> None:
    # Import hooks must be exercised without cached Bokeh modules.
    result = subprocess.run(
        [sys.executable, "-c", dedent(code)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_bokeh_import_does_not_load_submodules() -> None:
    run_in_subprocess(
        """
        import sys
        from marimo._output.formatters.formatters import register_formatters

        register_formatters()
        import bokeh

        assert "bokeh.models" not in sys.modules
        assert "bokeh.plotting" not in sys.modules
        assert "bokeh.io" not in sys.modules
        """
    )


@pytest.mark.parametrize("module_name", ["bokeh.io", "bokeh.plotting"])
def test_bokeh_unpatch(module_name: str) -> None:
    run_in_subprocess(
        f"""
        import importlib
        from marimo._output.formatters.bokeh_formatters import (
            BokehIOFormatter, BokehPlottingFormatter,
        )

        module = importlib.import_module({module_name!r})
        original = (module.show, module.output_notebook)
        factory = BokehIOFormatter() if {module_name!r} == "bokeh.io" else BokehPlottingFormatter()
        unpatch = factory.register()
        assert (module.show, module.output_notebook) != original
        unpatch()
        assert (module.show, module.output_notebook) == original
        """
    )


def test_concurrent_bokeh_imports() -> None:
    run_in_subprocess(
        """
        import importlib
        import importlib._bootstrap
        import importlib.machinery
        import sys
        import threading
        import time
        from concurrent.futures import ThreadPoolExecutor
        from marimo._output.formatters.formatters import register_formatters

        started = threading.Event()
        release = threading.Event()
        original_find_spec = importlib.machinery.PathFinder.find_spec

        class Finder:
            def find_spec(self, fullname, path=None, target=None):
                if fullname != "bokeh":
                    return None
                spec = original_find_spec(fullname, path, target)
                original_exec = spec.loader.exec_module

                def exec_module(module):
                    original_exec(module)
                    started.set()
                    assert release.wait(5)

                spec.loader.exec_module = exec_module
                return spec

        sys.meta_path.insert(0, Finder())
        register_formatters()
        with ThreadPoolExecutor(max_workers=2) as pool:
            root = pool.submit(importlib.import_module, "bokeh")
            try:
                assert started.wait(5)
                models = pool.submit(importlib.import_module, "bokeh.models")
                # Wait until the second import holds the child module lock
                # and must wait for the first import to release its parent.
                deadline = time.monotonic() + 5
                lock = importlib._bootstrap._get_module_lock("bokeh.models")
                while lock.owner is None:
                    assert time.monotonic() < deadline
                    time.sleep(0.001)
            finally:
                release.set()
            root.result(timeout=10)
            models.result(timeout=10)

        from bokeh.models import Div
        from marimo._output.formatting import get_formatter

        model = Div(text="concurrent import")
        formatter = get_formatter(model)
        assert formatter is not None
        mimetype, html = formatter(model)
        assert mimetype == "text/html"
        assert "<iframe" in html
        """
    )


@pytest.mark.parametrize("pre_import", [False, True])
@pytest.mark.parametrize("theme", ["light", "dark"])
@pytest.mark.parametrize(
    "module_name",
    ["bokeh.models", "bokeh.document", "bokeh.io", "bokeh.plotting"],
)
def test_bokeh_rendering(
    module_name: str, theme: str, pre_import: bool
) -> None:
    run_in_subprocess(
        f"""
        import importlib
        from unittest.mock import call, patch
        from marimo._output.formatters.formatters import register_formatters
        from marimo._output.formatting import get_formatter

        if {pre_import}:
            importlib.import_module({module_name!r})
        register_formatters(theme={theme!r})
        importlib.import_module({module_name!r})

        from bokeh.document import Document
        from bokeh.models import Div

        model = Div(text="Bokeh output")
        document = Document()
        document.add_root(model)
        for obj in [model, document]:
            formatter = get_formatter(obj)
            assert formatter is not None
            mimetype, html = formatter(obj)
            assert mimetype == "text/html"
            assert "<iframe" in html
            assert "Bokeh output" in html

        from bokeh import io, plotting
        from bokeh.themes import built_in_themes, default

        expected_theme = built_in_themes["dark_minimal"] if {theme!r} == "dark" else default
        assert io.curdoc().theme is expected_theme

        with patch("marimo._runtime.output._output.append") as append:
            for module in [io, plotting]:
                module.show(model)
                module.show(obj=model)
                module.output_notebook()
            assert append.call_args_list == [call(model)] * 4
        """
    )
