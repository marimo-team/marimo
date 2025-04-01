from __future__ import annotations

import pytest

from marimo._output.show_code import show_code, substitute_show_code_with_arg
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


async def test_show_code_position_above(
    k: Kernel, exec_req: ExecReqProvider
) -> None:
    await k.run(
        [
            exec_req.get(
                'import marimo as mo; x = mo.show_code(1, position="above")'
            )
        ]
    )
    result = k.globals["x"].text
    assert "<marimo-code-editor" in result, (
        "Expected '<marimo-code-editor>' in output but not found"
    )
    assert "<span>1</span>" in result, (
        "Expected '<span>1</span>' in output but not found"
    )
    assert result.index("<marimo-code-editor") < result.index(
        "<span>1</span>"
    ), "Code should appear before output"


async def test_show_code_position_below(
    k: Kernel, exec_req: ExecReqProvider
) -> None:
    await k.run(
        [
            exec_req.get(
                'import marimo as mo; x = mo.show_code(1, position="below")'
            )
        ]
    )
    result = k.globals["x"].text
    assert "<marimo-code-editor" in result, (
        "Expected '<marimo-code-editor>' in output but not found"
    )
    assert "<span>1</span>" in result, (
        "Expected '<span>1</span>' in output but not found"
    )
    assert result.index("<span>1</span>") < result.index(
        "<marimo-code-editor"
    ), "Output should appear before code"


async def test_show_code_position_left(
    k: Kernel, exec_req: ExecReqProvider
) -> None:
    await k.run(
        [
            exec_req.get(
                'import marimo as mo; x = mo.show_code(1, position="left")'
            )
        ]
    )
    result = k.globals["x"].text
    assert "<marimo-code-editor" in result, (
        "Expected '<marimo-code-editor>' in output but not found"
    )
    assert "<span>1</span>" in result, (
        "Expected '<span>1</span>' in output but not found"
    )
    assert result.index("<marimo-code-editor") < result.index(
        "<span>1</span>"
    ), "Code should appear before output"


async def test_show_code_position_right(
    k: Kernel, exec_req: ExecReqProvider
) -> None:
    await k.run(
        [
            exec_req.get(
                'import marimo as mo; x = mo.show_code(1, position="right")'
            )
        ]
    )
    result = k.globals["x"].text
    assert "<marimo-code-editor" in result, (
        "Expected '<marimo-code-editor>' in output but not found"
    )
    assert "<span>1</span>" in result, (
        "Expected '<span>1</span>' in output but not found"
    )
    assert result.index("<span>1</span>") < result.index(
        "<marimo-code-editor"
    ), "Output should appear before code"


async def test_show_code_position_default(
    k: Kernel, exec_req: ExecReqProvider
) -> None:
    await k.run([exec_req.get("import marimo as mo; x = mo.show_code(1)")])
    result = k.globals["x"].text
    assert "<marimo-code-editor" in result, (
        "Expected '<marimo-code-editor>' in output but not found"
    )
    assert "<span>1</span>" in result, (
        "Expected '<span>1</span>' in output but not found"
    )
    assert result.index("<span>1</span>") < result.index(
        "<marimo-code-editor"
    ), "Output should appear before code"


def test_fails_if_with_bad_args() -> None:
    with pytest.raises(AssertionError):
        show_code(1, position="foo")

    with pytest.raises(TypeError):
        show_code(1, "below")

    with pytest.raises(AssertionError):
        show_code(1, position=None)


def test_substitute_show_code_removes_position() -> None:
    # Basic cases
    code = 'mo.show_code(1, position="above")'
    assert substitute_show_code_with_arg(code) == "1"

    code = 'mo.show_code(1, position="below")'
    assert substitute_show_code_with_arg(code) == "1"

    code = 'mo.show_code(foo(1) + 1, position="above")'
    assert substitute_show_code_with_arg(code) == "foo(1) + 1"

    # Single quote in string
    code = "mo.show_code('hello, world', position='above')"
    assert substitute_show_code_with_arg(code) == "'hello, world'"

    code = "mo.show_code('hello, world', position='below')"
    assert substitute_show_code_with_arg(code) == "'hello, world'"

    # Case with extra spaces
    code = 'mo.show_code(   42   ,    position =  "above"   )'
    assert substitute_show_code_with_arg(code) == "42"

    code = 'mo.show_code(foo(2), bar(3), position="above")'
    assert substitute_show_code_with_arg(code) == "foo(2), bar(3)"

    code = "mo.show_code(100)"
    assert substitute_show_code_with_arg(code) == "100"

    code = "mo.show_code(foo(bar(5)))"
    assert substitute_show_code_with_arg(code) == "foo(bar(5))"

    code = 'mo.show_code(mo.show_code(1), position="above")'
    assert substitute_show_code_with_arg(code) == "mo.show_code(1)"

    code = 'mo.show_code(mo.show_code(foo(3) + 1, position="below"), position="above")'
    assert (
        substitute_show_code_with_arg(code)
        == 'mo.show_code(foo(3) + 1, position="below")'
    )

    code = 'mo.show_code((x + y) * 2, position="above")'
    assert substitute_show_code_with_arg(code) == "(x + y) * 2"

    code = "mo.show_code({'a': 1, 'b': 2}, position=\"below\")"
    assert substitute_show_code_with_arg(code) == "{'a': 1, 'b': 2}"

    code = 'mo.show_code([i for i in range(10)], position="above")'
    assert substitute_show_code_with_arg(code) == "[i for i in range(10)]"

    code = "mo.show_code()"
    assert substitute_show_code_with_arg(code) == ""

    code = 'mo.show_code(, position="above")'
    assert substitute_show_code_with_arg(code) == ""

    code = 'mo.show_code("hello, world", position="above")'
    assert substitute_show_code_with_arg(code) == '"hello, world"'

    code = "mo.show_code('single quotes test', position=\"below\")"
    assert substitute_show_code_with_arg(code) == "'single quotes test'"

    code = 'mo.show_code(mo.show_code(1, position="below"), position="above")'
    assert (
        substitute_show_code_with_arg(code)
        == 'mo.show_code(1, position="below")'
    )

    code = 'mo.show_code(mo.show_code(foo(3) + 1, position="below"), position="above")'
    assert (
        substitute_show_code_with_arg(code)
        == 'mo.show_code(foo(3) + 1, position="below")'
    )

    code = 'mo.show_code(mo.show_code(42, position="above"), position="below")'
    assert (
        substitute_show_code_with_arg(code)
        == 'mo.show_code(42, position="above")'
    )

    code = """mo.show_code(
        42,
        position=\"above\",
    )"""
    assert substitute_show_code_with_arg(code) == "42"

    code = """mo.show_code(
        42,
        position=\"above\",
    )"""
    assert substitute_show_code_with_arg(code) == "42"

    # Nested calls with different positions
    code = 'mo.show_code(mo.show_code(1, position="above"), position="below")'
    assert (
        substitute_show_code_with_arg(code)
        == 'mo.show_code(1, position="above")'
    )

    # Calls with additional whitespace and line breaks
    code = 'mo.show_code(\n    mo.show_code(42, position="above"),\n    position="below"\n)'
    assert (
        substitute_show_code_with_arg(code)
        == 'mo.show_code(42, position="above")'
    )

    # Calls with complex expressions
    code = 'mo.show_code((lambda x: x + 1)(5), position="above")'
    assert substitute_show_code_with_arg(code) == "(lambda x: x + 1)(5)"

    code = 'mo.show_code([i**2 for i in range(5)], position="below")'
    assert substitute_show_code_with_arg(code) == "[i**2 for i in range(5)]"

    code = 'mo.show_code({"key": "value"}, position="above")'
    assert substitute_show_code_with_arg(code) == '{"key": "value"}'


@pytest.mark.xfail(
    reason="Doesn't handle complex expressions for position",
    strict=True,
)
def test_fails_if_complex_expression_for_position() -> None:
    code = 'mo.show_code(10, position="above" if 1 else "below")'
    assert substitute_show_code_with_arg(code) == "10"
