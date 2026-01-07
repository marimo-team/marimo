# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import ast
import copy
import functools
import inspect
import itertools
from collections.abc import Awaitable
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, NoReturn, TypeVar, cast

from marimo._ast.cell import Cell
from marimo._ast.parse import ast_parse
from marimo._runtime.context import ContextNotInitializedError, get_context

if TYPE_CHECKING:
    from collections.abc import Mapping
    from inspect import FrameInfo

Fn = TypeVar("Fn", bound=Callable[..., Any])


MARIMO_TEST_STUB_NAME = "MarimoTestBlock"

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
    PYTEST_BASE = ast_parse(inspect.getsource(_pytest_scaffold))

    # We modify the signature of the cell function such that pytest
    # does not attempt to use the arguments as fixtures.

    args = {arg.arg: arg for arg in func_body.args.args}
    if allowed is None:
        allowed = [arg for arg in args.keys()]
    name = func_body.name

    # Typing checks for mypy - template structure is known
    fn = copy.deepcopy(PYTEST_BASE)
    body = fn.body[0]
    if not isinstance(body, ast.FunctionDef):
        raise ValueError("Invalid pytest scaffold template structure")
    returned = body.body[-1]
    if not isinstance(returned, ast.Return):
        raise ValueError("Invalid pytest scaffold template structure")
    call = returned.value
    if not isinstance(call, ast.Call):
        raise ValueError("Invalid pytest scaffold template structure")

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

    response = local[name]
    if not callable(response):
        raise ValueError(
            f"Expected callable for '{name}', got {type(response)}"
        )
    return response


def wrap_fn_for_pytest(func: Fn, cell: Cell) -> Callable[..., Any]:
    func_ast = ast_parse(inspect.getsource(func))
    func_body = func_ast.body[0]
    if not isinstance(func_body, (ast.FunctionDef, ast.AsyncFunctionDef)):
        raise ValueError(
            f"Expected function definition, got {type(func_body).__name__}"
        )

    args = {arg.arg: arg for arg in func_body.args.args}
    fixtures = [arg for arg in args.keys() if arg.endswith("_fixture")]
    reserved = set(args.keys()) - set(fixtures)
    # The remaining expected attributes are needed to ensure attribute count
    # matches.
    cell._pytest_reserved = reserved

    return build_stub_fn(
        func_body, inspect.getfile(func), cell.__call__, fixtures
    )


def is_pytest_decorator(decorator: ast.AST) -> tuple[bool, str | None]:
    """Check if decorator is a pytest.* call and return attr name."""
    # @pytest.fixture() or @pytest.mark.parametrize()
    if isinstance(decorator, ast.Call) and isinstance(
        decorator.func, ast.Attribute
    ):
        if (
            isinstance(decorator.func.value, ast.Name)
            and decorator.func.value.id == "pytest"
        ):
            return True, decorator.func.attr
        # @pytest.mark.parametrize() etc
        if (
            isinstance(decorator.func.value, ast.Attribute)
            and isinstance(decorator.func.value.value, ast.Name)
            and decorator.func.value.value.id == "pytest"
        ):
            return True, None  # Nested attr, use eval
    # @pytest.fixture (no call)
    if isinstance(decorator, ast.Attribute):
        if (
            isinstance(decorator.value, ast.Name)
            and decorator.value.id == "pytest"
        ):
            return True, decorator.attr
    return False, None


def has_fixture_decorator(node: ast.AST) -> bool:
    """Check if function has @pytest.fixture decorator."""
    if not hasattr(node, "decorator_list"):
        return False
    if len(node.decorator_list) != 1:
        return False
    decorator = node.decorator_list[0]
    # @fixture or @fixture()
    if isinstance(decorator, ast.Name) and decorator.id == "fixture":
        return True
    if isinstance(decorator, ast.Call):
        func = decorator.func
        if isinstance(func, ast.Name) and func.id == "fixture":
            return True
    # @pytest.fixture or @pytest.fixture()
    is_pytest, attr = is_pytest_decorator(decorator)
    return is_pytest and attr == "fixture"


def _eval_fixture_decorator(
    decorator: ast.AST,
    local: dict[str, Any],
    file: str,
) -> Callable[..., Any]:
    """Evaluate @pytest.fixture decorator, return decorator fn."""
    import pytest  # type: ignore

    if isinstance(decorator, ast.Call):
        fixture_args = [
            eval(compile(ast.Expression(arg), file, "eval"), local)
            for arg in decorator.args
        ]
        fixture_kwargs = {
            kw.arg: eval(
                compile(ast.Expression(kw.value), file, "eval"), local
            )
            for kw in decorator.keywords
            if kw.arg is not None
        }
        return cast(
            Callable[..., Any], pytest.fixture(*fixture_args, **fixture_kwargs)
        )
    else:
        return cast(Callable[..., Any], pytest.fixture)


def _make_fails(var: str, e: Exception) -> Callable[..., NoReturn]:
    """Create a hook that raises an error explaining the failure."""
    err = copy.copy(e)

    def fails(*args: Any, **kwargs: Any) -> NoReturn:
        del args, kwargs
        raise ValueError(
            f"Failed to evaluate decorator for '{var}'. "
            "Consider exposing relevant variables in app.setup."
        ) from err

    return fails


def _make_hook(
    var: str,
    run: Callable[
        [],
        tuple[Any, Mapping[str, Any]]
        | Awaitable[tuple[Any, Mapping[str, Any]]],
    ],
    use_wrapped: bool = False,
) -> Callable[..., Any]:
    """Single hook factory - handles both fixtures and tests."""

    def _hook(*args: Any, **kwargs: Any) -> Any:
        res = run()
        if isinstance(res, Awaitable):
            import asyncio

            loop = asyncio.new_event_loop()
            _, cell_defs = loop.run_until_complete(res)
        else:
            _, cell_defs = res

        target = cell_defs[var].__wrapped__ if use_wrapped else cell_defs[var]
        return target(*args, **kwargs)

    return _hook


def _build_hook(
    test: ast.FunctionDef | ast.AsyncFunctionDef,
    var: str,
    run: Callable[..., Any],
    file: str,
    local: dict[str, Any],
    is_fixture: bool = False,
) -> Callable[..., Any]:
    """Build hook for test or fixture function."""
    hook = _make_hook(var, run, use_wrapped=is_fixture)

    stub_fn = build_stub_fn(test, file)
    functools.wraps(stub_fn)(hook)

    try:
        if is_fixture:
            # Only apply the outer fixture decorator
            decorator = test.decorator_list[0]
            fixture_decorator = _eval_fixture_decorator(decorator, local, file)
            return cast(Callable[..., Any], fixture_decorator(hook))
        else:
            # Apply all decorators in reverse order
            for decorator in test.decorator_list[::-1]:
                expr = ast.Expression(decorator)
                hook = eval(compile(expr, file, "eval"), local)(hook)
    except Exception as e:
        return _make_fails(var, e)

    return hook


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
    frames: list[FrameInfo],
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
        if isinstance(node, (ast.Return, ast.Expr)):
            continue
        if not isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            if inner:
                continue
            # Unexpected, should be guarded to this point.
            raise RuntimeError(
                "Invalid test compilation. "
                " Please report to marimo-team/marimo/issues."
            )
        tests[node.name] = node

    # Pre-compute base locals once to avoid repeated inspect.stack() calls
    # which are expensive on Windows.
    base_local: dict[str, Any] = {}
    try:
        import pytest  # type: ignore

        base_local["pytest"] = pytest
    except ImportError:
        pass

    # Try to get context globals, or fall back to frame locals
    try:
        base_local.update(get_context().globals)
    except ContextNotInitializedError:
        # If not in runtime, we are running directly as a script. As
        # such, we need the values from the module frame.
        # Traverse frame upwards until we match the file.
        for frame in frames:
            if Path(frame.filename).resolve() == Path(file).resolve():
                base_local.update(frame.frame.f_locals)
                break

    def hook(var: str) -> Callable[..., Any] | type[MarimoTest]:
        test = tests.get(var, None)
        if test is None:

            def fails(*args: Any, **kwargs: Any) -> NoReturn:
                del args, kwargs
                raise ValueError(
                    f"Could not find test {var}, please report to"
                    "marimo-team/marimo/issues."
                )

            return fails

        if isinstance(test, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Use pre-computed locals
            local = base_local.copy()

            is_fixture = has_fixture_decorator(test)
            _hook = _build_hook(test, var, run, file, local, is_fixture)

            if not inner:
                _hook = staticmethod(_hook)

            return _hook

        elif isinstance(test, ast.ClassDef):
            class_defs = {
                node.name for node in test.body if hasattr(node, "name")
            }

            def _run() -> tuple[Any, Any]:
                old_output, old_defs = run()  # type: ignore
                old_defs = dict(old_defs)
                for d in class_defs:
                    old_defs[d] = getattr(old_defs[var], d)
                return old_output, old_defs

            return build_test_class(
                test.body, _run, file, var, class_defs, frames, True
            )
        raise ValueError(
            "Improperly compiled as a test. Please report to"
            "marimo-team/marimo/issues."
        )

    attrs = {var: h for var in defs if (h := hook(var)) is not None}
    return type(name, (MarimoTest,), attrs)


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
    cell._test_allowed = False

    tree = ast_parse(inspect.getsource(func))
    run = functools.cache(cell.run)

    # Must be a unique name, otherwise won't be injected properly.
    name = f"{MARIMO_TEST_STUB_NAME}_{next(block_incrementer)}"

    scope = tree.body[0]
    if not isinstance(
        scope, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
    ):
        raise ValueError(
            f"Expected function or class definition, got {type(scope).__name__}"
        )
    # Get first frame not in library to insert the class.
    # May be multiple levels if called from pytest or something.
    frames = inspect.stack(context=0)

    cls = build_test_class(
        scope.body, run, inspect.getfile(func), name, cell.defs, frames
    )

    # ensure marimo/_ not in frame path, using this file as a reference.
    library = Path(__file__).parent.parent
    for frame in frames:
        if library not in Path(frame.filename).parents:
            # Insert the class into the frame.
            frame.frame.f_locals[cls.__name__] = cls
            break
