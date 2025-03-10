from marimo._output.show_code import substitute_show_code_with_arg
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


def test_substitute_show_code() -> None:
    code = "mo.show_code()"
    assert substitute_show_code_with_arg(code) == ""

    code = "mo.show_code(1)"
    assert substitute_show_code_with_arg(code) == "1"

    code = "mo.show_code(foo(1) + 1)"
    assert substitute_show_code_with_arg(code) == "foo(1) + 1"

    code = "mo.show_code(mo.show_code(1))"
    assert substitute_show_code_with_arg(code) == "mo.show_code(1)"

    code = """
mo.show_code(
'''
hello, world
'''
)
"""
    assert (
        substitute_show_code_with_arg(code)
        == """'''
hello, world
'''"""
    )

    code = """
mo.show_code(
foo(1) + '''
hello, world
'''
)
"""
    assert (
        substitute_show_code_with_arg(code)
        == """foo(1) + '''
hello, world
'''"""
    )


async def test_show_code_code_first_true(
    k: Kernel, exec_req: ExecReqProvider
) -> None:
    await k.run(
        [
            exec_req.get(
                "import marimo as mo; x = mo.show_code(1, code_first=True)"
            )
        ]
    )
    result = k.globals["x"].text
    print("Debug Output (code_first=True):", result)  # Print actual output
    assert "<marimo-code-editor" in result, (
        "Expected '<marimo-code-editor>' in output but not found"
    )
    assert "<span>1</span>" in result, (
        "Expected '<span>1</span>' in output but not found"
    )
    assert result.index("<marimo-code-editor") < result.index(
        "<span>1</span>"
    ), "Code should appear before output"


async def test_show_code_code_first_false(
    k: Kernel, exec_req: ExecReqProvider
) -> None:
    await k.run(
        [
            exec_req.get(
                "import marimo as mo; x = mo.show_code(1, code_first=False)"
            )
        ]
    )
    result = k.globals["x"].text
    print("Debug Output (code_first=False):", result)  # Print actual output
    assert "<marimo-code-editor" in result, (
        "Expected '<marimo-code-editor>' in output but not found"
    )
    assert "<span>1</span>" in result, (
        "Expected '<span>1</span>' in output but not found"
    )
    assert result.index("<span>1</span>") < result.index(
        "<marimo-code-editor"
    ), "Output should appear before code"


async def test_show_code_code_first_default(
    k: Kernel, exec_req: ExecReqProvider
) -> None:
    await k.run([exec_req.get("import marimo as mo; x = mo.show_code(1)")])
    result = k.globals["x"].text
    print("Debug Output (code_first=False):", result)  # Print actual output
    assert "<marimo-code-editor" in result, (
        "Expected '<marimo-code-editor>' in output but not found"
    )
    assert "<span>1</span>" in result, (
        "Expected '<span>1</span>' in output but not found"
    )
    assert result.index("<span>1</span>") < result.index(
        "<marimo-code-editor"
    ), "Output should appear before code"


def test_substitute_show_code_removes_code_first() -> None:
    # Basic cases
    code = "mo.show_code(1, code_first=True)"
    assert substitute_show_code_with_arg(code) == "1"

    code = "mo.show_code(1, code_first=False)"
    assert substitute_show_code_with_arg(code) == "1"

    code = "mo.show_code(foo(1) + 1, code_first=True)"
    assert substitute_show_code_with_arg(code) == "foo(1) + 1"

    # Case with extra spaces
    code = "mo.show_code(   42   ,    code_first =  True   )"
    assert substitute_show_code_with_arg(code) == "42"

    code = "mo.show_code(foo(2), bar(3), code_first=True)"
    assert substitute_show_code_with_arg(code) == "foo(2), bar(3)"

    code = "mo.show_code(100)"
    assert substitute_show_code_with_arg(code) == "100"

    code = "mo.show_code(foo(bar(5)))"
    assert substitute_show_code_with_arg(code) == "foo(bar(5))"

    code = "mo.show_code(mo.show_code(1), code_first=True)"
    assert substitute_show_code_with_arg(code) == "mo.show_code(1)"

    code = "mo.show_code(mo.show_code(foo(3) + 1, code_first=False), code_first=True)"
    assert (
        substitute_show_code_with_arg(code)
        == "mo.show_code(foo(3) + 1, code_first=False)"
    )

    code = "mo.show_code((x + y) * 2, code_first=True)"
    assert substitute_show_code_with_arg(code) == "(x + y) * 2"

    code = "mo.show_code({'a': 1, 'b': 2}, code_first=False)"
    assert substitute_show_code_with_arg(code) == "{'a': 1, 'b': 2}"

    code = "mo.show_code([i for i in range(10)], code_first=True)"
    assert substitute_show_code_with_arg(code) == "[i for i in range(10)]"

    code = "mo.show_code()"
    assert substitute_show_code_with_arg(code) == ""

    code = "mo.show_code(, code_first=True)"
    assert substitute_show_code_with_arg(code) == ""

    code = 'mo.show_code("hello, world", code_first=True)'
    assert substitute_show_code_with_arg(code) == '"hello, world"'

    code = "mo.show_code('single quotes test', code_first=False)"
    assert substitute_show_code_with_arg(code) == "'single quotes test'"

    code = "mo.show_code(mo.show_code(1, code_first=False), code_first=True)"
    assert (
        substitute_show_code_with_arg(code)
        == "mo.show_code(1, code_first=False)"
    )

    code = "mo.show_code(mo.show_code(foo(3) + 1, code_first=False), code_first=True)"
    assert (
        substitute_show_code_with_arg(code)
        == "mo.show_code(foo(3) + 1, code_first=False)"
    )

    code = "mo.show_code(mo.show_code(42, code_first=True), code_first=False)"
    assert (
        substitute_show_code_with_arg(code)
        == "mo.show_code(42, code_first=True)"
    )
