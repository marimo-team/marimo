from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest

from marimo._runtime import context
from marimo._runtime.context.types import ExecutionContext
from marimo._runtime.runtime import Kernel
from tests.conftest import ExecReqProvider

if TYPE_CHECKING:
    import duckdb


async def test_context_installed(
    execution_kernel: Kernel, exec_req: ExecReqProvider
) -> None:
    k = execution_kernel
    await k.run(
        [
            exec_req.get(
                """
                import marimo as mo

                installed = mo._runtime.context.runtime_context_installed()
                """
            )
        ]
    )

    assert k.globals["installed"]


def test_context_not_installed() -> None:
    assert not context.runtime_context_installed()


def test_not_running_in_notebook() -> None:
    from marimo._runtime.context.utils import running_in_notebook

    assert not running_in_notebook()


def test_execution_context_restores_connection_after_error() -> None:
    execution_context = ExecutionContext(
        cell_id="cell_id", setting_element_value=False
    )
    original_connection = cast("duckdb.DuckDBPyConnection", object())
    replacement_connection = cast("duckdb.DuckDBPyConnection", object())
    execution_context.duckdb_connection = original_connection

    def run_failing_cell() -> None:
        with execution_context.with_connection(replacement_connection):
            assert (
                execution_context.duckdb_connection is replacement_connection
            )
            raise RuntimeError("cell failed")

    with pytest.raises(RuntimeError, match="cell failed"):
        run_failing_cell()

    assert execution_context.duckdb_connection is original_connection


async def test_is_embedded(
    execution_kernel: Kernel, exec_req: ExecReqProvider
) -> None:
    """Test that is_embedded() returns True when parent context exists."""
    k = execution_kernel
    await k.run(
        [
            exec_req.get(
                """
                import marimo as mo
                from marimo._runtime.context.types import get_context

                # In the main kernel, there's no parent, so is_embedded is False
                ctx = get_context()
                is_embedded_main = ctx.is_embedded()
                """
            )
        ]
    )
    assert not k.errors
    assert not k.globals["is_embedded_main"]


async def test_is_embedded_in_app_embed(
    execution_kernel: Kernel, exec_req: ExecReqProvider
) -> None:
    """Test that is_embedded() returns True inside an embedded app."""
    k = execution_kernel
    await k.run(
        [
            exec_req.get(
                """
                from marimo import App

                app = App()

                @app.cell
                def _():
                    from marimo._runtime.context.types import get_context
                    ctx = get_context()
                    is_embedded_inner = ctx.is_embedded()
                    return (is_embedded_inner,)
                """
            ),
            exec_req.get(
                """
                result = await app.embed()
                is_embedded_in_app = result.defs["is_embedded_inner"]
                """
            ),
        ]
    )
    assert not k.errors
    # Inside the embedded app, is_embedded should return True
    assert k.globals["is_embedded_in_app"]
