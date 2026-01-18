from marimo._runtime import context
from marimo._runtime.runtime import Kernel
from tests.conftest import ExecReqProvider


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
