# Copyright 2024 Marimo. All rights reserved.
import ast
import copy
import inspect
from typing import Any, Callable, TypeVar, cast

from marimo._ast.cell import Cell

Fn = TypeVar("Fn", bound=Callable[..., Any])


# Python definition used as the ast bones for constructing a pytest function.
def _pytest_scaffold(stub: Any) -> Any:
    return stub(stub=stub)


def wrap_fn_for_pytest(func: Fn, cell: Cell) -> Callable[..., Any]:
    # Avoid declaring the function in the global scope, since it may cause
    # issues with meta-analysis tools like cxfreeze (see #3828).
    PYTEST_BASE = ast.parse(inspect.getsource(_pytest_scaffold))

    # We modify the signature of the cell function such that pytest
    # does not attempt to use the arguments as fixtures.

    func_ast = ast.parse(inspect.getsource(func))
    func_body = func_ast.body[0]
    assert isinstance(func_body, (ast.FunctionDef, ast.AsyncFunctionDef))

    args = {arg.arg: arg for arg in func_body.args.args}
    fixtures = [arg for arg in args.keys() if arg.endswith("_fixture")]
    reserved = set(args.keys()) - set(fixtures)
    name = func.__name__

    # Typing checks for mypy
    fn = copy.deepcopy(PYTEST_BASE)
    body = fn.body[0]
    assert isinstance(body, ast.FunctionDef)
    returned = body.body[-1]
    assert isinstance(returned, ast.Return)
    call = returned.value
    assert isinstance(call, ast.Call)

    # Using _pytest_scaffold as a template, the resultant function will look
    # like:
    #
    # ```python
    # def name_of_fn_passed(vars_ending_in_fixture, ...) -> Any:
    #     return cell(vars_ending_in_fixture=vars_ending_in_fixture)
    # ```
    #
    # Which is sufficient to fool pytest.
    body.args.args[:] = [
        ast.arg(arg, lineno=args[arg].lineno, col_offset=args[arg].col_offset)
        for arg in fixtures
    ]
    (_call_stub,) = call.keywords
    call.keywords = [
        ast.keyword(
            arg=arg,
            value=ast.Name(
                arg,
                ctx=ast.Load(),
                lineno=args[arg].lineno,
                col_offset=args[arg].col_offset,
            ),
            lineno=args[arg].lineno,
            col_offset=args[arg].col_offset,
        )
        for arg in fixtures
    ]
    body.name = name
    local = {"stub": cell.__call__, "Any": Any}
    eval(compile(fn, inspect.getfile(func), "exec"), local)

    # The remaining expected attributes are needed to ensure attribute count
    # matches.
    cell._pytest_reserved = reserved

    response = cast(Callable[..., Any], local[name])
    assert callable(response)
    return response
