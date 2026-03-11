from __future__ import annotations

import textwrap
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
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
