# Copyright 2025 Marimo. All rights reserved.

from __future__ import annotations

import builtins

from marimo._ast import toplevel
from marimo._ast.app import App, InternalApp
from marimo._ast.toplevel import (
    TopLevelExtraction,
    TopLevelStatus,
    TopLevelType,
)

BUILTINS = set(builtins.__dict__.keys())


class TestTopLevelStatus:
    @staticmethod
    def test_expression_ignored(app) -> None:
        @app.cell
        def cell():
            def add(a: int, b: int) -> int:
                return a + b

            pass

        status = TopLevelStatus.from_cell(cell._cell, BUILTINS)
        assert status.type == TopLevelType.CELL
        assert status.hint == toplevel.HINT_NOT_SINGLE

    @staticmethod
    def test_function_converted(app) -> None:
        @app.cell
        def cell():
            def add(a: int, b: int) -> int:
                return a + b

        status = TopLevelStatus.from_cell(cell._cell, BUILTINS)
        assert status.type == TopLevelType.TOPLEVEL

    @staticmethod
    def test_function_uses_top(app) -> None:
        with app.setup:
            c = 1e-16

        @app.cell
        def cell():
            def add(a: int, b: int, offset: float = c) -> float:
                return a + b + offset

        status = TopLevelStatus.from_cell(cell._cell, BUILTINS | {"c"})
        assert status.type == TopLevelType.TOPLEVEL

    @staticmethod
    def test_function_uses_top_fn(app) -> None:
        @app.cell
        def _():
            def c() -> float:
                return 1e-16

        @app.cell
        def cell(c):
            def add(a: int, b: int, offset: float = c()) -> float:
                return a + b + offset

        status = TopLevelStatus.from_cell(cell._cell, BUILTINS | {"c"})
        assert status.type == TopLevelType.TOPLEVEL

    @staticmethod
    def test_function_uses_top_fn_bad_order(app) -> None:
        @app.cell
        def cell(c):
            def add(a: int, b: int, offset: float = c()) -> float:
                return a + b + offset

        @app.cell
        def _():
            def c() -> float:
                return 1e-16

        status = TopLevelStatus.from_cell(cell._cell, BUILTINS)
        status.update(BUILTINS, set(), {"c"})
        assert status.type == TopLevelType.CELL
        assert status.hint == toplevel.HINT_ORDER_DEPENDENT.format({"c"})

    @staticmethod
    def test_function_not_top(app) -> None:
        @app.cell
        def _():
            c = 1e-16
            return c

        @app.cell
        def cell(c):
            def add(a: int, b: int, offset: float = c) -> float:
                return a + b + offset

        status = TopLevelStatus.from_cell(cell._cell, BUILTINS)
        assert status.type == TopLevelType.CELL
        assert status.hint == toplevel.HINT_HAS_REFS.format({"c"})

    @staticmethod
    def test_injection_name_ignored(app) -> None:
        @app.cell
        def app():
            def app(a: int, b: int) -> int:
                return a + b

        status = TopLevelStatus.from_cell(app._cell, BUILTINS)
        assert status.type == TopLevelType.CELL
        assert status.hint == toplevel.HINT_BAD_NAME

    @staticmethod
    def test_function_recursion(app) -> None:
        @app.cell
        def cell():
            def fib(n: int) -> int:
                if n <= 1:
                    return 1
                return fib(n - 1) + fib(n - 2)

        @app.cell
        def _(fib):
            assert fib(6) == 13

        status = TopLevelStatus.from_cell(cell._cell, BUILTINS)
        assert status.type == TopLevelType.TOPLEVEL


class TestTopLevelExtraction:
    @staticmethod
    def test_function_uses_top(app) -> None:
        with app.setup:
            c = 1e-16

        @app.cell
        def cell():
            def add(a: int, b: int, offset: float = c) -> float:
                return a + b + offset

        extraction = TopLevelExtraction.from_app(InternalApp(app))
        assert [TopLevelType.TOPLEVEL] == [s.type for s in extraction]

    @staticmethod
    def test_decorator_reversed(app) -> None:
        with app.setup:
            from typing import Callable

        @app.cell
        def second(wrap):
            @wrap
            def c() -> float:
                return 1 + 1

        @app.cell
        def first():
            def wrap(fn: Callable[[], float]) -> float:
                return lambda: fn() + 1

        extraction = TopLevelExtraction.from_app(InternalApp(app))
        assert [TopLevelType.CELL, TopLevelType.TOPLEVEL] == [
            s.type for s in extraction
        ], [s.hint for s in extraction]

    @staticmethod
    def test_decorator(app) -> None:
        with app.setup:
            from typing import Callable

        @app.cell
        def first():
            def wrap(fn: Callable[[], float]) -> float:
                return lambda: fn() + 1

        @app.cell
        def second(wrap):
            @wrap
            def c() -> float:
                return 1 + 1

        extraction = TopLevelExtraction.from_app(InternalApp(app))
        assert [TopLevelType.TOPLEVEL, TopLevelType.TOPLEVEL] == [
            s.type for s in extraction
        ], [s.hint for s in extraction]

    @staticmethod
    def test_function_trailing_comment(app) -> None:
        @app.cell
        def cell():
            def add(a: int, b: int) -> float:
                return a + b

            # Comment

        extraction = TopLevelExtraction.from_app(InternalApp(app))
        assert [TopLevelType.CELL] == [s.type for s in extraction]
        assert extraction.statuses[0].hint == toplevel.HINT_HAS_COMMENT

    @staticmethod
    def test_function_trailing_comment_ok(app) -> None:
        @app.cell
        def cell():
            def add(a: int, b: int) -> float:
                return a + b
                # Comment

        @app.cell
        def tricky_cell():
            def md() -> float:
                return """
            #"""

        extraction = TopLevelExtraction.from_app(InternalApp(app))
        assert [TopLevelType.TOPLEVEL, TopLevelType.TOPLEVEL] == [
            s.type for s in extraction
        ]

    @staticmethod
    def test_function_uses_top_fn_unresolved(app) -> None:
        @app.cell
        def cell(c):
            def add(a: int, b: int) -> int:
                return a + b + c()

        @app.cell
        def _():
            def c() -> float:
                return 1e-16

        status = TopLevelStatus.from_cell(cell._cell, BUILTINS)
        status.update(BUILTINS, set(), {"c"})
        assert status.type == TopLevelType.UNRESOLVED

        extraction = TopLevelExtraction.from_app(InternalApp(app))
        assert [TopLevelType.TOPLEVEL, TopLevelType.TOPLEVEL] == [
            s.type for s in extraction
        ], [s.hint for s in extraction]

    @staticmethod
    def test_function_uses_top_fn_unresolved_path(app) -> None:
        @app.cell
        def cell(A, Z):
            def a() -> float:
                return A() + Z()

        @app.cell
        def _(B):
            def A() -> float:
                return B()

        @app.cell
        def _():
            def B() -> float:
                return 1.0

        @app.cell
        def _():
            def Y() -> float:
                return 1.0

        @app.cell
        def _(Y):
            def Z() -> float:
                return Y()

        status = TopLevelStatus.from_cell(cell._cell, BUILTINS)
        status.update(BUILTINS, set(), {"A", "B", "Y", "Z"})
        assert status.type == TopLevelType.UNRESOLVED

        extraction = TopLevelExtraction.from_app(InternalApp(app))
        assert [
            TopLevelType.TOPLEVEL,
        ] * 5 == [s.type for s in extraction], [s.hint for s in extraction]

    @staticmethod
    def test_function_uses_top_fn_unresolved_path_fails(app) -> None:
        @app.cell
        def cell(A, Z):
            def a() -> float:
                return A() + Z()

        @app.cell
        def _(B):
            def A() -> float:
                return B()

        @app.cell
        def _():
            def B() -> float:
                return 1.0

        @app.cell
        def _():
            def Y() -> float:
                return 1.0

            pass  # to make it a cell

        @app.cell
        def _(Y):
            def Z() -> float:
                return Y()

        status = TopLevelStatus.from_cell(cell._cell, BUILTINS)
        status.update(BUILTINS, set(), {"A", "B", "Y", "Z"})
        assert status.type == TopLevelType.UNRESOLVED

        extraction = TopLevelExtraction.from_app(InternalApp(app))
        assert [
            TopLevelType.CELL,
            TopLevelType.TOPLEVEL,
            TopLevelType.TOPLEVEL,
            TopLevelType.CELL,
            TopLevelType.CELL,
        ] == [s.type for s in extraction], [s.hint for s in extraction]
        assert extraction.statuses[
            0
        ].hint == toplevel.HINT_HAS_CLOSE_REFS.format({"Z"})

    @staticmethod
    def test_indirect_recursion() -> None:
        app = App()
        # Needed for consistent stack trace paths.
        app._anonymous_file = True

        # Renders, but fails in runtime (which is fine).
        @app.cell
        def first(c):
            def add(a: int, b: int) -> int:
                return a + b + c()

        @app.cell
        def second(add):
            def c() -> float:
                return add(1, 1)

        status = TopLevelStatus.from_cell(first._cell, BUILTINS)
        status.update(BUILTINS, set(), {"c", "add"})
        assert status.type == TopLevelType.UNRESOLVED

        status = TopLevelStatus.from_cell(second._cell, BUILTINS)
        status.update(BUILTINS, {"add"}, {"c", "add"})
        assert status.type == TopLevelType.UNRESOLVED

        extraction = TopLevelExtraction.from_app(InternalApp(app))
        assert [TopLevelType.TOPLEVEL, TopLevelType.TOPLEVEL] == [
            s.type for s in extraction
        ], [s.hint for s in extraction]

    @staticmethod
    def test_name_is_not_propagated(app) -> None:
        @app.cell
        def cell():
            value = 1

        @app.function
        def to_be_demoted():
            return value + 1  # type: ignore # noqa: F821

        extraction = TopLevelExtraction.from_app(InternalApp(app))
        assert [
            TopLevelType.CELL,
            TopLevelType.CELL,
        ] == [s.type for s in extraction], [s.hint for s in extraction]
        assert ["cell", "_"] == [s.name for s in extraction], [
            s.hint for s in extraction
        ]

    @staticmethod
    def test_variables_extracted(app) -> None:
        with app.setup:
            CONSTANT: int = 42

        @app.cell
        def _():
            x: int = 2
            # No typing
            z = CONSTANT
            return (x, z)

        @app.cell
        def _():
            y: float = 2.0
            return (y,)

        extraction = TopLevelExtraction.from_app(InternalApp(app))

        from marimo._ast.visitor import AnnotationData, VariableData

        assert extraction.variables == {
            "x": VariableData(
                kind="variable",
                required_refs={
                    "int",
                },
                unbounded_refs=set(),
                annotation_data=AnnotationData(
                    repr="int",
                    refs={
                        "int",
                    },
                ),
                import_data=None,
            ),
            "y": VariableData(
                kind="variable",
                required_refs={
                    "float",
                },
                unbounded_refs=set(),
                annotation_data=AnnotationData(
                    repr="float",
                    refs={
                        "float",
                    },
                ),
                import_data=None,
            ),
            "z": VariableData(
                kind="variable",
                required_refs={
                    "CONSTANT",
                },
                unbounded_refs=set(),
                annotation_data=None,
                import_data=None,
            ),
        }


class TestTopLevelClasses:
    @staticmethod
    def test_class_converted(app) -> None:
        @app.cell
        def cell():
            class Example: ...

        extraction = TopLevelExtraction.from_app(InternalApp(app))
        assert [
            TopLevelType.TOPLEVEL,
        ] == [s.type for s in extraction], [s.hint for s in extraction]

    @staticmethod
    def test_subclassing_order(app) -> None:
        @app.cell
        def Example():
            class Example: ...

        @app.cell
        def SubExample(Example):
            class SubExample(Example): ...

        extraction = TopLevelExtraction.from_app(InternalApp(app))
        assert [
            TopLevelType.TOPLEVEL,
            TopLevelType.TOPLEVEL,
        ] == [s.type for s in extraction], [s.hint for s in extraction]

    @staticmethod
    def test_subclassing_scoped_vars(app) -> None:
        @app.cell
        def Example():
            class Example: ...

        @app.cell
        def SubExample(A, Example):
            class SubExample(Example):
                def __init__(self):
                    self.a = A()

        @app.cell
        def _():
            def A() -> float:
                return 1.0

        extraction = TopLevelExtraction.from_app(InternalApp(app))
        assert [
            TopLevelType.TOPLEVEL,
            TopLevelType.TOPLEVEL,
            TopLevelType.TOPLEVEL,
        ] == [s.type for s in extraction], [s.hint for s in extraction]

    @staticmethod
    def test_subclassing_order_vars(app) -> None:
        @app.cell
        def Example(A):
            class Example:
                a = A()

        @app.cell
        def _():
            def A() -> float:
                return 1.0

        extraction = TopLevelExtraction.from_app(InternalApp(app))
        assert [
            TopLevelType.CELL,
            TopLevelType.TOPLEVEL,
        ] == [s.type for s in extraction], [s.hint for s in extraction]

    @staticmethod
    def test_subclassing_order_vars_recursion(app) -> None:
        @app.cell
        def Example(A):
            class Example:
                class SubExample:
                    a = A()

        @app.cell
        def _():
            def A() -> float:
                return 1.0

        extraction = TopLevelExtraction.from_app(InternalApp(app))
        assert [
            TopLevelType.CELL,
            TopLevelType.TOPLEVEL,
        ] == [s.type for s in extraction], [s.hint for s in extraction]

    @staticmethod
    def test_subclassing_order_breaks(app) -> None:
        @app.cell
        def cell(Example):
            class SubExample(Example): ...

        @app.cell
        def _():
            class Example: ...

        extraction = TopLevelExtraction.from_app(InternalApp(app))
        assert [
            TopLevelType.CELL,
            TopLevelType.TOPLEVEL,
        ] == [s.type for s in extraction], [s.hint for s in extraction]

    @staticmethod
    def test_class_properties(app) -> None:
        @app.class_definition
        class Example:
            @property
            def prop(self) -> int:
                return 1

            @prop.setter
            def prop(self, value: int) -> None:
                pass

        @app.function
        def f():
            return Example()

        extraction = TopLevelExtraction.from_app(InternalApp(app))
        assert [
            TopLevelType.TOPLEVEL,
            TopLevelType.TOPLEVEL,
        ] == [s.type for s in extraction], [s.hint for s in extraction]

    @staticmethod
    def test_class_invocation(app) -> None:
        @app.class_definition
        class Example: ...

        @app.function
        def f():
            return Example()

        extraction = TopLevelExtraction.from_app(InternalApp(app))
        assert [
            TopLevelType.TOPLEVEL,
            TopLevelType.TOPLEVEL,
        ] == [s.type for s in extraction], [s.hint for s in extraction]


class TestTopLevelHook:
    @staticmethod
    def test_toplevel_hook(app) -> None:
        @app.class_definition
        class Example: ...

        @app.cell()
        def f():
            def f():
                return Example()

        extraction = TopLevelExtraction.from_graph(
            f._cell,
            InternalApp(app).graph,
        )
        assert [
            TopLevelType.TOPLEVEL,
            TopLevelType.TOPLEVEL,
        ] == [s.type for s in extraction], [s.hint for s in extraction]
