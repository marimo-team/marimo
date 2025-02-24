# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import ast
import copy
import functools
import inspect
import itertools
from pathlib import Path
from typing import Any, Awaitable, Callable, Mapping, NoReturn, TypeVar, cast

from marimo._ast.cell import Cell

Fn = TypeVar("Fn", bound=Callable[..., Any])


block_incrementer = itertools.count()


class MarimoTest:
    """Base class for Marimo tests."""

    __test__ = True


# Python definition used as the ast bones for constructing a pytest function.
def _pytest_scaffold(stub: Any) -> Any:
    return stub(stub=stub)


def build_stub_fn(
    func_body: ast.FunctionDef | ast.AsyncFunctionDef,
    file: str = "",
    basis: None | Callable[..., Any] = None,
    allowed: None | list[str] = None,
) -> Callable[..., Any]:
    # Avoid declaring the function in the global scope, since it may cause
    # issues with meta-analysis tools like cxfreeze (see #3828).
    PYTEST_BASE = ast.parse(inspect.getsource(_pytest_scaffold))

    # We modify the signature of the cell function such that pytest
    # does not attempt to use the arguments as fixtures.

    args = {arg.arg: arg for arg in func_body.args.args}
    if allowed is None:
        allowed = [arg for arg in args.keys() if arg != "self"]
    name = func_body.name

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
        for arg in allowed
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
        for arg in allowed
    ]
    body.name = name
    local = {"stub": basis, "Any": Any}
    eval(compile(fn, file, "exec"), local)

    response = cast(Callable[..., Any], local[name])
    assert callable(response)
    return response


def wrap_fn_for_pytest(func: Fn, cell: Cell) -> Callable[..., Any]:
    func_ast = ast.parse(inspect.getsource(func))
    func_body = func_ast.body[0]
    assert isinstance(func_body, (ast.FunctionDef, ast.AsyncFunctionDef))

    args = {arg.arg: arg for arg in func_body.args.args}
    fixtures = [arg for arg in args.keys() if arg.endswith("_fixture")]
    reserved = set(args.keys()) - set(fixtures)
    # The remaining expected attributes are needed to ensure attribute count
    # matches.
    cell._pytest_reserved = reserved

    return build_stub_fn(
        func_body, inspect.getfile(func), cell.__call__, fixtures
    )


def build_test_class(
    body: list[ast.stmt],
    run: Callable[
        [],
        tuple[Any, Mapping[str, Any]]
        | Awaitable[tuple[Any, Mapping[str, Any]]],
    ],
    file: str,
    name: str,
    defs: set[str],
    inner: bool = False,
) -> type[MarimoTest]:
    """
    Build a test class from the body of a cell.

    @app.cell
    def _(many, potential, deps):
        def test_one_of_many_tests_in_a_given_cell():
            assert True

        class TestSubclass:
            def test_subclass_method_works(self):
                assert True

    ->

    class MarimoTestBlock_idx(MarimoTest):
        @staticmethod
        def test_one_of_many_tests_in_a_given_cell():
            ...
        class TestSubclass(MarimoTest):
            def test_subclass_method_works(self):
                assert True

    Note that each test is resolved symbolically such that breaking test
    definitions do not change the suite definition/ stop the entire suite from
    running. Relatively marginal overhead.
    """
    tests = {}
    for node in body:
        assert isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ), (
            "Invalid test compilation. "
            " Please report to marimo-team/marimo/issues."
        )
        tests[node.name] = node

    def hook(var: str) -> Callable[..., Any] | type[MarimoTest]:
        def _hook(*args: Any, **kwargs: Any) -> Any:
            _, defs = run()  # type: ignore
            return defs[var](*args, **kwargs)

        test = tests.get(var, None)
        if test is None:

            def fails(*args: Any, **kwargs: Any) -> NoReturn:
                del args, kwargs
                raise ValueError(
                    (
                        f"Could not find test {var}, please report to"
                        "marimo-team/marimo/issues."
                    )
                )

            return fails

        if isinstance(test, (ast.FunctionDef, ast.AsyncFunctionDef)):
            stub_fn = build_stub_fn(test, file)
            functools.wraps(stub_fn)(_hook)
            # Evaluate and run decorators.
            local = {}
            try:
                import pytest  # type: ignore

                # TODO: Remove import pytest with top level functions
                # Just a hack for now.
                local = {"pytest": pytest}
            except ImportError:
                pass

            try:
                for decorator in test.decorator_list[::-1]:
                    expr = ast.Expression(decorator)
                    _hook = eval(compile(expr, file, "eval"), local)(_hook)
                if not inner:
                    _hook = staticmethod(_hook)
            except Exception as _e:
                # Python restricts scope of exceptions artificially.
                e = copy.copy(_e)

                def fails(*args: Any, **kwargs: Any) -> NoReturn:
                    del args, kwargs
                    raise ValueError(
                        (
                            f"Failed to evaluate decorator for {var}."
                            "Consider adjusting the test to enable "
                            "static analysis."
                        )
                    ) from e

                functools.wraps(stub_fn)(fails)
                return fails

            return _hook
        elif isinstance(test, ast.ClassDef):
            defs = {
                node.name
                for node in test.body
                if isinstance(
                    node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
                )
                and node.name.lower().startswith("test")
            }

            def _run() -> tuple[Any, Any]:
                old_output, old_defs = run()  # type: ignore
                old_defs = dict(old_defs)
                for d in defs:
                    old_defs[d] = getattr(old_defs[var], d)
                return old_output, old_defs

            return build_test_class(test.body, _run, file, var, defs, True)
        raise ValueError(
            (
                "Improperly compiled as a test. Please report to"
                "marimo-team/marimo/issues."
            )
        )

    return type(name, (MarimoTest,), {var: hook(var) for var in defs})


def process_for_pytest(func: Fn, cell: Cell) -> None:
    # Check if it is considered a __test__ cell.
    if not cell.__test__:
        return

    # If this is declared as a test on the top level, leave it alone.
    if cell.name.startswith("test_"):
        # Set the correct signature for the function.
        functools.wraps(wrap_fn_for_pytest(func, cell))(cell)
        return

    # Turn off test for the cell itself in this case.
    cell._test = False

    tree = ast.parse(inspect.getsource(func))
    run = functools.cache(cell.run)

    # Must be a unique name, otherwise won't be injected properly.
    name = f"MarimoTestBlock_{next(block_incrementer)}"

    scope = tree.body[0]
    assert isinstance(
        scope, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
    )
    cls = build_test_class(
        scope.body, run, inspect.getfile(func), name, cell.defs
    )
    # Get first frame not in library to insert the class.
    # May be multiple levels if called from pytest or something.
    frames = inspect.stack()

    # ensure marimo/_ not in frame path, using this file as a reference.
    library = Path(__file__).parent.parent
    for frame in frames:
        if library not in Path(frame.filename).parents:
            # Insert the class into the frame.
            frame.frame.f_locals[cls.__name__] = cls
            break
