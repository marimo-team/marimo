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
