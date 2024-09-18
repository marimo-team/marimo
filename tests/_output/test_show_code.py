from marimo._runtime.runtime import Kernel
from tests.conftest import ExecReqProvider


async def test_show_code_basic(k: Kernel, exec_req: ExecReqProvider) -> None:
    await k.run([exec_req.get("import marimo as mo; x = mo.show_code(1)")])
    assert "x = 1" in k.globals["x"].text


async def test_show_code_no_output(
    k: Kernel, exec_req: ExecReqProvider
) -> None:
    await k.run([exec_req.get("import marimo as mo; x = mo.show_code()")])
    assert "import marimo as mo; x =" in k.globals["x"].text, k.globals[
        "x"
    ].text
    assert "mo.show_code()" not in k.globals["x"].text


async def test_show_code_multiline(
    k: Kernel, exec_req: ExecReqProvider
) -> None:
    await k.run(
        [
            exec_req.get(
                """
                import marimo as mo;
                x = mo.show_code('''
                hello world
                '''
                )
                """
            )
        ]
    )
    assert "hello world" in k.globals["x"].text
    assert "(" not in k.globals["x"].text
    assert ")" not in k.globals["x"].text
    assert "mo.show_code" not in k.globals["x"].text
