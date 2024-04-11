# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import ast
from inspect import cleandoc

import pytest

from marimo._ast import visitor
from marimo._ast.visitor import VariableData


def test_assign_simple() -> None:
    expr = "x = 0"
    v = visitor.ScopedVisitor()
    mod = ast.parse(expr)
    v.visit(mod)
    assert v.defs == set(["x"])
    assert v.refs == set()
    assert v.variable_data == {"x": VariableData(kind="variable")}


def test_multiple_assign() -> None:
    expr = "x = y = 0"
    v = visitor.ScopedVisitor()
    mod = ast.parse(expr)
    v.visit(mod)
    assert v.defs == set(["x", "y"])
    assert v.refs == set()
    assert v.variable_data == {
        "x": VariableData(kind="variable"),
        "y": VariableData(kind="variable"),
    }


def test_assign_multiple_statements() -> None:
    code = "x = 0\ny = 0"
    v = visitor.ScopedVisitor()
    mod = ast.parse(code)
    v.visit(mod)
    assert v.defs == set(["x", "y"])
    assert v.refs == set()
    assert v.variable_data == {
        "x": VariableData(kind="variable"),
        "y": VariableData(kind="variable"),
    }


def test_assign_attr() -> None:
    expr = "x.a = 0"
    v = visitor.ScopedVisitor()
    mod = ast.parse(expr)
    v.visit(mod)
    assert v.defs == set()
    assert v.refs == set(["x"])
    assert not v.variable_data


def test_read_attr() -> None:
    expr = "x.a"
    v = visitor.ScopedVisitor()
    mod = ast.parse(expr)
    v.visit(mod)
    assert v.defs == set()
    assert v.refs == set(["x"])
    assert not v.variable_data


def test_read_attr_of_defined_variable() -> None:
    expr = "x = 0; x.a"
    v = visitor.ScopedVisitor()
    mod = ast.parse(expr)
    v.visit(mod)
    assert v.defs == set(["x"])
    assert v.refs == set()
    assert v.variable_data == {"x": VariableData(kind="variable")}


def test_assign_nested_attr() -> None:
    expr = "x.a.b = 0"
    v = visitor.ScopedVisitor()
    mod = ast.parse(expr)
    v.visit(mod)
    assert v.defs == set()
    assert v.refs == set(["x"])
    assert not v.variable_data


def test_read_nested_attr() -> None:
    expr = "x.a.b"
    v = visitor.ScopedVisitor()
    mod = ast.parse(expr)
    v.visit(mod)
    assert v.defs == set()
    assert v.refs == set(["x"])
    assert not v.variable_data


def test_assign_same_name() -> None:
    expr = "x = x"
    v = visitor.ScopedVisitor()
    mod = ast.parse(expr)
    v.visit(mod)
    assert v.defs == set(["x"])
    assert v.refs == set(["x"])
    assert v.variable_data == {"x": VariableData(kind="variable")}

    expr = "(x := x)"
    v = visitor.ScopedVisitor()
    mod = ast.parse(expr)
    v.visit(mod)
    assert v.defs == set(["x"])
    assert v.refs == set(["x"])
    assert v.variable_data == {"x": VariableData(kind="variable")}

    expr = "x += x"
    v = visitor.ScopedVisitor()
    mod = ast.parse(expr)
    v.visit(mod)
    assert v.defs == set(["x"])
    assert v.refs == set(["x"])
    assert v.variable_data == {"x": VariableData(kind="variable")}

    expr = "def f(): x = x; return x"
    v = visitor.ScopedVisitor()
    mod = ast.parse(expr)
    v.visit(mod)
    assert v.defs == set(["f"])
    assert v.refs == set(["x"])
    assert v.variable_data == {"f": VariableData(kind="function")}

    expr = "class F(): x = x"
    v = visitor.ScopedVisitor()
    mod = ast.parse(expr)
    v.visit(mod)
    assert v.defs == set(["F"])
    assert v.refs == set(["x"])
    assert v.variable_data == {"F": VariableData(kind="class")}

    expr = "{x: x}"
    v = visitor.ScopedVisitor()
    mod = ast.parse(expr)
    v.visit(mod)
    assert v.defs == set()
    assert v.refs == set(["x"])
    assert not v.variable_data


def test_load_attr() -> None:
    expr = "x.a"
    v = visitor.ScopedVisitor()
    mod = ast.parse(expr)
    v.visit(mod)
    assert v.defs == set()
    assert v.refs == set(["x"])
    assert not v.variable_data


def test_structured_assignment() -> None:
    expr = "(a, (b, c, (d, e)), (f, g), h) = 0"
    v = visitor.ScopedVisitor()
    mod = ast.parse(expr)
    v.visit(mod)
    names = set(["a", "b", "c", "d", "e", "f", "g", "h"])
    assert v.defs == names
    assert v.refs == set()
    assert v.variable_data == {
        "a": VariableData(kind="variable"),
        "b": VariableData(kind="variable"),
        "c": VariableData(kind="variable"),
        "d": VariableData(kind="variable"),
        "e": VariableData(kind="variable"),
        "f": VariableData(kind="variable"),
        "g": VariableData(kind="variable"),
        "h": VariableData(kind="variable"),
    }


def test_starred_assignment() -> None:
    expr = "a, *b = 0"
    v = visitor.ScopedVisitor()
    mod = ast.parse(expr)
    v.visit(mod)
    assert v.defs == set(["a", "b"])
    assert v.refs == set()
    assert v.variable_data == {
        "a": VariableData(kind="variable"),
        "b": VariableData(kind="variable"),
    }


def test_scope_does_not_leak() -> None:
    code = "\n".join(
        [
            "def foo():",
            "  z = 0",
            "z",
        ]
    )
    v = visitor.ScopedVisitor()
    mod = ast.parse(code)
    v.visit(mod)
    assert v.defs == set(["foo"])
    assert v.refs == set("z")
    assert v.variable_data == {
        "foo": VariableData(kind="function"),
    }


def test_nested_comprehensions() -> None:
    code = "\n".join(
        [
            "[(i, j) for i in range(10) for j in range(i)]",
            "{(i, j) for i in range(10) for j in range(i)}",
            "{i: j for i in range(10) for j in range(i)}",
        ]
    )
    v = visitor.ScopedVisitor()
    mod = ast.parse(code)
    v.visit(mod)
    assert v.defs == set()
    assert v.refs == set(["range"])
    assert not v.variable_data


def test_walrus_leaks_to_global_in_comprehension() -> None:
    code = "\n".join(
        [
            "def foo(): a",
            "[(a := (i, (b := j))) for i in range(10) for j in range(i)]",
            "{(c := (i, j)) for i in range(10) for j in range(i)}",
            "{i: (d := j) for i in range(10) for j in range(i)}",
        ]
    )
    v = visitor.ScopedVisitor()
    mod = ast.parse(code)
    v.visit(mod)
    assert v.defs == set(["a", "b", "c", "d", "foo"])
    # "a" should not be a ref!
    assert v.refs == set(["range"])
    assert v.variable_data == {
        "a": VariableData(kind="variable"),
        "b": VariableData(kind="variable"),
        "c": VariableData(kind="variable"),
        "d": VariableData(kind="variable"),
        "foo": VariableData(kind="function"),
    }


def test_nested_walrus_leaks_to_global_in_comprehension() -> None:
    code = "[[(a := (i, (b := j))) for j in range(i)] for i in range(10)]"
    v = visitor.ScopedVisitor()
    mod = ast.parse(code)
    v.visit(mod)
    assert v.defs == set(["a", "b"])
    assert v.refs == set(["range"])
    assert v.variable_data == {
        "a": VariableData(kind="variable"),
        "b": VariableData(kind="variable"),
    }


def test_pep572_walrus_comprehension_examples() -> None:
    code = "[(x, y, x/y) for x in input_data if (y := f(x)) > 0]"
    v = visitor.ScopedVisitor()
    mod = ast.parse(code)
    v.visit(mod)
    assert v.defs == set(["y"])
    assert v.refs == set(["input_data", "f"])
    assert v.variable_data == {
        "y": VariableData(kind="variable"),
    }

    code = "[[y := f(x), x/y] for x in range(5)]"
    v = visitor.ScopedVisitor()
    mod = ast.parse(code)
    v.visit(mod)
    assert v.defs == set(["y"])
    assert v.refs == set(["f", "range"])
    assert v.variable_data == {
        "y": VariableData(kind="variable"),
    }


def test_walrus_in_comp_in_fn_block_does_not_leak_to_global() -> None:
    code = "\n".join(
        ["def f():", "  [(x := 0) for i in range(5)]", "  y = x + 1"]
    )
    v = visitor.ScopedVisitor()
    mod = ast.parse(code)
    v.visit(mod)
    assert v.defs == set(["f"])  # x should _not_ leak to global scope
    assert v.refs == set(["range"])  # x should leak to f's scope
    assert v.variable_data == {
        "f": VariableData(kind="function"),
    }


def test_assignments_in_multiple_scopes() -> None:
    code = "\n".join(
        [
            "a = 0",
            "def foo():",
            "  b = 0",
            "  c = 0",
            "  def bar():",
            "    d = 0",
            "e = 0",
        ]
    )
    v = visitor.ScopedVisitor()
    mod = ast.parse(code)
    v.visit(mod)
    assert v.defs == set(["a", "e", "foo"])
    assert v.refs == set()
    assert v.variable_data == {
        "a": VariableData(kind="variable"),
        "e": VariableData(kind="variable"),
        "foo": VariableData(kind="function"),
    }


def test_function_with_args() -> None:
    code = cleandoc(
        """
        def foo(a: 'annotation', b=1, c=2, *d, e, f=3, **g):
          y = a + z
          return y
        """
    )
    v = visitor.ScopedVisitor()
    mod = ast.parse(code)
    v.visit(mod)
    assert v.defs == set(["foo"])
    assert v.refs == set("z")
    assert v.variable_data == {
        "foo": VariableData(kind="function"),
    }


def test_function_with_defaults() -> None:
    code = cleandoc(
        """
        def foo(x=y, y=x, z=a):
          pass
        """
    )
    v = visitor.ScopedVisitor()
    mod = ast.parse(code)
    v.visit(mod)
    assert v.defs == set(["foo"])
    assert v.refs == set(["x", "y", "a"])
    assert v.variable_data == {
        "foo": VariableData(kind="function"),
    }


def test_async_function_def() -> None:
    code = cleandoc(
        """
        async def foo(a):
          y = a + z

        x  = 0
        """
    )
    v = visitor.ScopedVisitor()
    mod = ast.parse(code)
    v.visit(mod)
    assert v.defs == set(["foo", "x"])
    assert v.refs == set("z")
    assert v.variable_data == {
        "foo": VariableData(kind="function"),
        "x": VariableData(kind="variable"),
    }


def test_global_def() -> None:
    code = cleandoc(
        """
        def foo(a):
          global x
          x = 0
        """
    )
    v = visitor.ScopedVisitor()
    mod = ast.parse(code)
    v.visit(mod)
    assert v.defs == set(["foo", "x"])
    assert v.refs == set()
    assert v.variable_data == {
        "foo": VariableData(kind="function"),
        "x": VariableData(kind="variable"),
    }


def test_global_ref() -> None:
    code = cleandoc(
        """
        def foo(a):
          global x
          print(x)
        """
    )
    v = visitor.ScopedVisitor()
    mod = ast.parse(code)
    v.visit(mod)
    assert v.defs == set(["foo"])
    assert v.refs == set(["x", "print"])
    assert v.variable_data == {
        "foo": VariableData(kind="function"),
    }


def test_nested_local_def_and_global_ref() -> None:
    code = cleandoc(
        """
        def foo(a):
          global x
          def bar():
            x = 10
          print(x)
        """
    )
    v = visitor.ScopedVisitor()
    mod = ast.parse(code)
    v.visit(mod)
    assert v.defs == set(["foo"])
    assert v.refs == set(["x", "print"])
    assert v.variable_data == {
        "foo": VariableData(kind="function"),
    }


def test_call_ref() -> None:
    code = "foo()"
    v = visitor.ScopedVisitor()
    mod = ast.parse(code)
    v.visit(mod)
    assert v.defs == set()
    assert v.refs == set(["foo"])
    assert not v.variable_data


def test_call_defined() -> None:
    # fmt: off
    code = "\n".join([
        "def foo():",
        "  pass",
        "foo()"
    ])
    # fmt: on
    v = visitor.ScopedVisitor()
    mod = ast.parse(code)
    v.visit(mod)
    assert v.defs == set(["foo"])
    assert v.refs == set()
    assert v.variable_data == {
        "foo": VariableData(kind="function"),
    }


def test_mutation_generates_def() -> None:
    code = "x += 5"
    mod = ast.parse(code)
    v = visitor.ScopedVisitor()
    v.visit(mod)
    assert v.defs == set(["x"])
    assert v.refs == set()
    assert v.variable_data == {
        "x": VariableData(kind="variable"),
    }


def test_captured_variables() -> None:
    code = cleandoc(
        """
        x = 0

        def f():
            x
        """
    )
    mod = ast.parse(code)
    v = visitor.ScopedVisitor()
    v.visit(mod)
    assert v.defs == set(["f", "x"])
    assert v.refs == set([])

    code = cleandoc(
        """
        def f():
            x

        x = 0
        """
    )
    mod = ast.parse(code)
    v = visitor.ScopedVisitor()
    v.visit(mod)
    assert v.defs == set(["f", "x"])
    assert v.refs == set([])

    code = cleandoc(
        """
        def f():
            def g():
                x

        x = 0
        """
    )
    mod = ast.parse(code)
    v = visitor.ScopedVisitor()
    v.visit(mod)
    assert v.defs == set(["f", "x"])
    assert v.refs == set([])

    code = cleandoc(
        """
        def f():
            def g():
                x
            x = 0
        """
    )
    mod = ast.parse(code)
    v = visitor.ScopedVisitor()
    v.visit(mod)
    assert v.defs == set(["f"])
    assert v.refs == set([])

    code = cleandoc(
        """
        def f():
            def g():
                x

        def h():
            x = 1
        """
    )
    mod = ast.parse(code)
    v = visitor.ScopedVisitor()
    v.visit(mod)
    assert v.defs == set(["f", "h"])
    assert v.refs == set(["x"])


@pytest.mark.skipif("sys.version_info < (3, 10)")
def test_matchas() -> None:
    code = cleandoc(
        """
        match value:
            case [a]:
                ...
            case (b, c):
                ...
            case d:
                ...
            case e as f:
                ...
        """
    )
    mod = ast.parse(code)
    v = visitor.ScopedVisitor()
    v.visit(mod)
    assert v.defs == set(["a", "b", "c", "d", "e", "f"])
    assert v.refs == set(["value"])
    assert v.variable_data == {
        "a": VariableData(kind="variable"),
        "b": VariableData(kind="variable"),
        "c": VariableData(kind="variable"),
        "d": VariableData(kind="variable"),
        "e": VariableData(kind="variable"),
        "f": VariableData(kind="variable"),
    }


@pytest.mark.skipif("sys.version_info < (3, 10)")
def test_matchstar() -> None:
    code = cleandoc(
        """
        match value:
            case [1, 2, *rest]:
                ...
            case [*_]:
                ...
        """
    )
    mod = ast.parse(code)
    v = visitor.ScopedVisitor()
    v.visit(mod)
    assert v.defs == set(["rest"])
    assert v.refs == set(["value"])
    assert v.variable_data == {
        "rest": VariableData(kind="variable"),
    }


@pytest.mark.skipif("sys.version_info < (3, 10)")
def test_matchmapping() -> None:
    code = cleandoc(
        """
        match value:
            case {1: _, 2: _, **a}:
                ...
            case {**b}:
                ...
            case {1: _}:
                ...
        """
    )
    mod = ast.parse(code)
    v = visitor.ScopedVisitor()
    v.visit(mod)
    assert v.defs == set(["a", "b"])
    assert v.refs == set(["value"])
    assert v.variable_data == {
        "a": VariableData(kind="variable"),
        "b": VariableData(kind="variable"),
    }


def test_import_nested() -> None:
    expr = "import a.b.c"
    v = visitor.ScopedVisitor()
    mod = ast.parse(expr)
    v.visit(mod)
    assert v.defs == set(["a"])
    assert v.refs == set()
    assert v.variable_data["a"] == VariableData(kind="import", module="a")


def test_import_as() -> None:
    expr = "import a.b.c as d"
    v = visitor.ScopedVisitor()
    mod = ast.parse(expr)
    v.visit(mod)
    assert v.defs == set(["d"])
    assert v.refs == set()
    assert v.variable_data["d"] == VariableData(kind="import", module="a")


def test_import_multiple() -> None:
    expr = "import a.b.c, d"
    v = visitor.ScopedVisitor()
    mod = ast.parse(expr)
    v.visit(mod)
    assert v.defs == set(["a", "d"])
    assert v.refs == set()
    assert v.variable_data["a"] == VariableData(kind="import", module="a")
    assert v.variable_data["d"] == VariableData(kind="import", module="d")


def test_from_import() -> None:
    expr = "from a.b.c import d"
    v = visitor.ScopedVisitor()
    mod = ast.parse(expr)
    v.visit(mod)
    assert v.defs == set(["d"])
    assert v.refs == set()
    assert v.variable_data["d"] == VariableData(
        kind="import", module="a", import_level=0
    )


def test_relative_from_import() -> None:
    expr = "from ..a.b.c import d"
    v = visitor.ScopedVisitor()
    mod = ast.parse(expr)
    v.visit(mod)
    assert v.defs == set(["d"])
    assert v.refs == set()
    assert v.variable_data["d"] == VariableData(
        kind="import", module="a", import_level=2
    )


def test_from_import_star() -> None:
    expr = "from a.b.c import *"
    v = visitor.ScopedVisitor()
    mod = ast.parse(expr)
    with pytest.raises(SyntaxError) as e:
        v.visit(mod)
    assert "`import *` is not allowed in marimo." in str(e)
    assert v.defs == set()
    assert v.refs == set()
    assert not v.variable_data


@pytest.mark.skipif("sys.version_info < (3, 12)")
def test_type_alias_scoped() -> None:
    expr = "type alias[T] = list[T]"
    v = visitor.ScopedVisitor()
    mod = ast.parse(expr)
    v.visit(mod)
    # T should not be among the refs or defs
    assert v.defs == set(["alias"])
    assert v.refs == set(["list"])


@pytest.mark.skipif("sys.version_info < (3, 12)")
def test_type_var_generic_class() -> None:
    expr = cleandoc(
        """
    class A[T]:
        def hello(self, x: T) -> T:
            T
    """
    )
    v = visitor.ScopedVisitor()
    mod = ast.parse(expr)
    v.visit(mod)
    # T should not be among the refs or defs
    assert v.defs == set(["A"])
    assert v.refs == set()


@pytest.mark.skipif("sys.version_info < (3, 12)")
def test_type_var_generic_function() -> None:
    expr = cleandoc(
        """
        def test[U](u: U) -> U:
            return u
        """
    )
    v = visitor.ScopedVisitor()
    mod = ast.parse(expr)
    v.visit(mod)
    assert v.defs == set(["test"])
    # U should not be a ref
    assert v.refs == set()
