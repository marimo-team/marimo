from __future__ import annotations

import textwrap
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

if TYPE_CHECKING:
    import pathlib

    from marimo._runtime.runtime import Kernel
    from tests.conftest import ExecReqProvider

_INNER_APP = textwrap.dedent(
    """\
    import marimo
    app = marimo.App()

    @app.cell
    def _():
        import polars as pl
        return (pl,)

    @app.cell
    def _(pl):
        cars = pl.DataFrame({"name": ["a", "b", "c"], "hp": [100, 200, 300]})
        return (cars,)

    @app.cell
    def _():
        import marimo as mo
        return (mo,)

    @app.cell
    def _(mo, cars):
        df = mo.sql("SELECT * FROM cars LIMIT 2")
        return (df,)
    """
)


@pytest.mark.requires("duckdb", "polars")
async def test_sql_cells_when_running_as_module(
    execution_kernel: Kernel,
    exec_req: ExecReqProvider,
    tmp_path: pathlib.Path,
) -> None:
    """SQL cells in an imported app see that app's globals, not the kernel's"""
    (tmp_path / "inner_app.py").write_text(_INNER_APP)

    k = execution_kernel
    await k.run(
        [
            exec_req.get(
                f"""
                import sys
                sys.path.insert(0, {str(tmp_path)!r})
                from inner_app import app as inner_app
                """
            ),
            exec_req.get(
                """
                _outputs, _defs = inner_app.run()
                sql_result = _defs["df"]
                """
            ),
        ]
    )
    assert not k.errors
    assert len(k.globals["sql_result"]) == 2


_FORMATTER_APP = textwrap.dedent(
    """\
    import marimo
    app = marimo.App()

    @app.cell
    def _():
        from marimo._output.formatters.df_formatters import include_opinionated
        from marimo._runtime.context import get_context, runtime_context_installed
        opinionated = include_opinionated()
        has_ctx = runtime_context_installed()
        return (opinionated, has_ctx)
    """
)


@pytest.mark.requires("polars")
async def test_formatter_config_in_nested_app_run(
    execution_kernel: Kernel,
    exec_req: ExecReqProvider,
    tmp_path: pathlib.Path,
) -> None:
    """Formatter config reads the inner script context, not the outer kernel's.

    Copilot flagged that register_formatters() runs before
    script_context.install(), so include_opinionated() might read the
    outer kernel's config.  This test forces the outer kernel to report
    display.dataframes="plain" (so include_opinionated would return False
    there) and verifies the inner app still sees the correct default.
    """
    (tmp_path / "fmt_app.py").write_text(_FORMATTER_APP)

    k = execution_kernel

    from marimo._runtime.context import get_context

    ctx = get_context()
    original_config = ctx.marimo_config
    patched_config = {**original_config}
    patched_config["display"] = {
        **original_config.get("display", {}),
        "dataframes": "plain",
    }

    with patch.object(
        type(ctx),
        "marimo_config",
        new_callable=lambda: property(lambda _self: patched_config),
    ):
        await k.run(
            [
                exec_req.get(
                    f"""
                    import sys
                    sys.path.insert(0, {str(tmp_path)!r})
                    from fmt_app import app as fmt_app
                    """
                ),
                exec_req.get(
                    """
                    _outputs, _defs = fmt_app.run()
                    opinionated = _defs["opinionated"]
                    has_ctx = _defs["has_ctx"]
                    """
                ),
            ]
        )

    assert not k.errors
    # The inner script context should be installed during cell execution
    assert k.globals["has_ctx"] is True
    # include_opinionated() should read the inner script context's config
    # (default="rich"), not the outer kernel's patched "plain" config
    assert k.globals["opinionated"] is True
