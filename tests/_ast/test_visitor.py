# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import ast
from inspect import cleandoc
from textwrap import dedent

import pytest

from marimo._ast import visitor
from marimo._ast.errors import ImportStarError
from marimo._ast.visitor import (
    AnnotationData,
    ImportData,
    VariableData,
    normalize_sql_f_string,
)
from marimo._dependencies.dependencies import DependencyManager


def test_assign_simple() -> None:
    expr = "x = 0"
    v = visitor.ScopedVisitor()
    mod = ast.parse(expr)
    v.visit(mod)
    assert v.defs == set(["x"])
    assert v.refs == set()
    assert v.variable_data == {"x": [VariableData(kind="variable")]}


def test_multiple_assign() -> None:
    expr = "x = y = 0"
    v = visitor.ScopedVisitor()
    mod = ast.parse(expr)
    v.visit(mod)
    assert v.defs == set(["x", "y"])
    assert v.refs == set()
    assert v.variable_data == {
        "x": [VariableData(kind="variable")],
        "y": [VariableData(kind="variable")],
    }


def test_assign_multiple_statements() -> None:
    code = "x = 0\ny = 0"
    v = visitor.ScopedVisitor()
    mod = ast.parse(code)
    v.visit(mod)
    assert v.defs == set(["x", "y"])
    assert v.refs == set()
    assert v.variable_data == {
        "x": [VariableData(kind="variable")],
        "y": [VariableData(kind="variable")],
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
    assert v.variable_data == {"x": [VariableData(kind="variable")]}


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
    assert v.variable_data == {
        "x": [VariableData(kind="variable", required_refs={"x"})]
    }

    expr = "x=1; x = x"
    v = visitor.ScopedVisitor()
    mod = ast.parse(expr)
    v.visit(mod)
    assert v.defs == set(["x"])
    assert v.refs == set()
    assert v.variable_data == {
        "x": [
            VariableData(kind="variable", required_refs=set()),
            VariableData(kind="variable", required_refs={"x"}),
        ]
    }

    expr = "(x := x)"
    v = visitor.ScopedVisitor()
    mod = ast.parse(expr)
    v.visit(mod)
    assert v.defs == set(["x"])
    assert v.refs == set(["x"])
    assert v.variable_data == {
        "x": [VariableData(kind="variable", required_refs={"x"})]
    }

    expr = "x += x"
    v = visitor.ScopedVisitor()
    mod = ast.parse(expr)
    v.visit(mod)
    assert v.defs == set(["x"])
    assert v.refs == set(["x"])
    assert v.variable_data == {
        "x": [VariableData(kind="variable", required_refs={"x"})]
    }

    expr = "def f(): x = x; return x"
    v = visitor.ScopedVisitor()
    mod = ast.parse(expr)
    v.visit(mod)
    assert v.defs == set(["f"])
    assert v.refs == set(["x"])
    assert v.variable_data == {
        "f": [
            VariableData(
                kind="function", required_refs={"x"}, unbounded_refs=set()
            )
        ]
    }

    expr = "class F(): x = x"
    v = visitor.ScopedVisitor()
    mod = ast.parse(expr)
    v.visit(mod)
    assert v.defs == set(["F"])
    assert v.refs == set(["x"])
    assert v.variable_data == {
        "F": [
            VariableData(
                kind="class", required_refs={"x"}, unbounded_refs={"x"}
            )
        ]
    }

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
        "a": [VariableData(kind="variable")],
        "b": [VariableData(kind="variable")],
        "c": [VariableData(kind="variable")],
        "d": [VariableData(kind="variable")],
        "e": [VariableData(kind="variable")],
        "f": [VariableData(kind="variable")],
        "g": [VariableData(kind="variable")],
        "h": [VariableData(kind="variable")],
    }


def test_starred_assignment() -> None:
    expr = "a, *b = 0"
    v = visitor.ScopedVisitor()
    mod = ast.parse(expr)
    v.visit(mod)
    assert v.defs == set(["a", "b"])
    assert v.refs == set()
    assert v.variable_data == {
        "a": [VariableData(kind="variable")],
        "b": [VariableData(kind="variable")],
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
        "foo": [VariableData(kind="function")],
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


def test_comprehension_generator() -> None:
    code = "\n".join(
        [
            "[x for x in x]",
        ]
    )
    v = visitor.ScopedVisitor()
    mod = ast.parse(code)
    v.visit(mod)
    assert v.defs == set()
    assert v.refs == set(["x"])
    assert not v.variable_data


def test_nested_comprehension_generator() -> None:
    code = "\n".join(
        [
            "[x for x in x for x in x]",
        ]
    )
    v = visitor.ScopedVisitor()
    mod = ast.parse(code)
    v.visit(mod)
    assert v.defs == set()
    assert v.refs == set(["x"])
    assert not v.variable_data


def test_nested_comprehension_generator_with_named_expr() -> None:
    code = "\n".join(
        [
            "[(x := x) for x in x for x in x]",
        ]
    )
    v = visitor.ScopedVisitor()
    mod = ast.parse(code)
    v.visit(mod)
    # named expr kicks x out, evicting the ref
    assert v.defs == set(["x"])
    assert v.refs == set()
    assert v.variable_data == {"x": [VariableData(kind="variable")]}


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
        "a": [VariableData(kind="variable")],
        "b": [VariableData(kind="variable")],
        "c": [VariableData(kind="variable")],
        "d": [VariableData(kind="variable")],
        "foo": [VariableData(kind="function", required_refs={"a"})],
    }


def test_nested_walrus_leaks_to_global_in_comprehension() -> None:
    code = "[[(a := (i, (b := j))) for j in range(i)] for i in range(10)]"
    v = visitor.ScopedVisitor()
    mod = ast.parse(code)
    v.visit(mod)
    assert v.defs == set(["a", "b"])
    assert v.refs == set(["range"])
    assert v.variable_data == {
        "a": [VariableData(kind="variable")],
        "b": [VariableData(kind="variable")],
    }


def test_pep572_walrus_comprehension_examples() -> None:
    code = "[(x, y, x/y) for x in input_data if (y := f(x)) > 0]"
    v = visitor.ScopedVisitor()
    mod = ast.parse(code)
    v.visit(mod)
    assert v.defs == set(["y"])
    assert v.refs == set(["input_data", "f"])
    assert v.variable_data == {
        "y": [VariableData(kind="variable")],
    }

    code = "[[y := f(x), x/y] for x in range(5)]"
    v = visitor.ScopedVisitor()
    mod = ast.parse(code)
    v.visit(mod)
    assert v.defs == set(["y"])
    assert v.refs == set(["f", "range"])
    assert v.variable_data == {
        "y": [VariableData(kind="variable")],
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
        "f": [VariableData(kind="function", required_refs={"range"})],
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
        "a": [VariableData(kind="variable")],
        "e": [VariableData(kind="variable")],
        "foo": [VariableData(kind="function")],
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
        "foo": [VariableData(kind="function", required_refs={"z"})],
    }


def test_annotations_captured() -> None:
    code = cleandoc(
        """
        x: int = CONSTANT + 2
        """
    )
    v = visitor.ScopedVisitor()
    mod = ast.parse(code)
    v.visit(mod)
    assert v.defs == set(["x"])
    assert v.refs == set(["int", "CONSTANT"])
    assert v.variable_data == {
        "x": [
            VariableData(
                kind="variable",
                required_refs={"CONSTANT", "int"},
                annotation_data=AnnotationData(repr="int", refs={"int"}),
            )
        ],
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
    # TODO: Are these required refs?
    assert v.variable_data == {
        "foo": [
            VariableData(
                kind="function",
                required_refs={"x", "y", "a"},
                unbounded_refs={"x", "y", "a"},
            )
        ],
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
        "foo": [VariableData(kind="function", required_refs={"z"})],
        "x": [VariableData(kind="variable")],
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
        "foo": [VariableData(kind="function", required_refs={"x"})],
        "x": [VariableData(kind="variable")],
    }


def test_global_not_ref() -> None:
    code = cleandoc(
        """
        x = 0
        def foo(a):
          global x
        """
    )
    v = visitor.ScopedVisitor()
    mod = ast.parse(code)
    v.visit(mod)
    assert v.defs == set(["foo", "x"])
    assert v.refs == set()


def test_global_not_ref_define_later() -> None:
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


def test_global_after_scoped_def() -> None:
    code = cleandoc(
        """
        def f():
            x = 0

            def g():
                global x
                x = 1
        """
    )
    v = visitor.ScopedVisitor()
    mod = ast.parse(code)
    v.visit(mod)
    assert v.defs == set(["f", "x"])
    assert not v.refs


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
        "foo": [VariableData(kind="function", required_refs={"x", "print"})],
    }


def test_global_deleted_ref() -> None:
    code = cleandoc(
        """
        def f():
            global x
            del x
        """
    )
    v = visitor.ScopedVisitor()
    mod = ast.parse(code)
    v.visit(mod)
    assert v.defs == set(["f"])
    assert v.refs == set(["x"])
    assert v.deleted_refs == {"x"}


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
        "foo": [VariableData(kind="function", required_refs={"x", "print"})],
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
        "foo": [VariableData(kind="function")],
    }


def test_mutation_generates_def() -> None:
    code = "x += 5"
    mod = ast.parse(code)
    v = visitor.ScopedVisitor()
    v.visit(mod)
    assert v.defs == set(["x"])
    assert v.refs == set()
    assert v.variable_data == {
        "x": [VariableData(kind="variable")],
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
        "a": [VariableData(kind="variable")],
        "b": [VariableData(kind="variable")],
        "c": [VariableData(kind="variable")],
        "d": [VariableData(kind="variable")],
        "e": [VariableData(kind="variable")],
        "f": [VariableData(kind="variable")],
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
        "rest": [VariableData(kind="variable")],
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
        "a": [VariableData(kind="variable")],
        "b": [VariableData(kind="variable")],
    }


def test_import_nested() -> None:
    expr = "import a.b.c"
    v = visitor.ScopedVisitor()
    mod = ast.parse(expr)
    v.visit(mod)
    assert v.defs == set(["a"])
    assert v.refs == set()
    assert v.variable_data["a"] == [
        VariableData(
            kind="import",
            import_data=ImportData(
                definition="a", module="a.b.c", imported_symbol=None
            ),
        )
    ]


def test_import_as() -> None:
    expr = "import a.b.c as d"
    v = visitor.ScopedVisitor()
    mod = ast.parse(expr)
    v.visit(mod)
    assert v.defs == set(["d"])
    assert v.refs == set()
    assert v.variable_data["d"] == [
        VariableData(
            kind="import",
            import_data=ImportData(
                definition="d", module="a.b.c", imported_symbol=None
            ),
        )
    ]


def test_import_multiple() -> None:
    expr = "import a.b.c, d"
    v = visitor.ScopedVisitor()
    mod = ast.parse(expr)
    v.visit(mod)
    assert v.defs == set(["a", "d"])
    assert v.refs == set()
    assert v.variable_data["a"] == [
        VariableData(
            kind="import",
            import_data=ImportData(
                definition="a", module="a.b.c", imported_symbol=None
            ),
        )
    ]
    assert v.variable_data["d"] == [
        VariableData(
            kind="import",
            import_data=ImportData(
                definition="d", module="d", imported_symbol=None
            ),
        )
    ]


def test_from_import() -> None:
    expr = "from a.b.c import d"
    v = visitor.ScopedVisitor()
    mod = ast.parse(expr)
    v.visit(mod)
    assert v.defs == set(["d"])
    assert v.refs == set()
    assert v.variable_data["d"] == [
        VariableData(
            kind="import",
            import_data=ImportData(
                definition="d",
                module="a.b.c",
                imported_symbol="a.b.c.d",
                import_level=0,
            ),
        )
    ]


def test_relative_from_import() -> None:
    expr = "from ..a.b.c import d"
    v = visitor.ScopedVisitor()
    mod = ast.parse(expr)
    v.visit(mod)
    assert v.defs == set(["d"])
    assert v.refs == set()
    assert v.variable_data["d"] == [
        VariableData(
            kind="import",
            import_data=ImportData(
                definition="d",
                module="a.b.c",
                imported_symbol="a.b.c.d",
                import_level=2,
            ),
        )
    ]


def test_from_import_star() -> None:
    expr = "from a.b.c import *"
    v = visitor.ScopedVisitor()
    mod = ast.parse(expr)
    with pytest.raises(ImportStarError) as e:
        v.visit(mod)
    assert "`import *` is not allowed in marimo." in str(e)
    assert v.defs == set()
    assert v.refs == set()
    assert not v.variable_data


def test_try_block() -> None:
    code = "\n".join(
        [
            "f = 2",
            "try:",
            "  v = 1 / 0",
            "except TypeError as e:",
            "  err = e",
            "  e = 0",
            "  x = out_of_scope",
            "  print(f'caught {type(e)} with nested {e.exceptions}')",
            "except OSError as f:",
            "  err2 = f",
            "  try:",
            "    y = 1 / 0",
            "  except ZeroDivisionError as g:",
            "    err3 = g",
            "else:",
            "  w = 1",
            "finally:",
            "  z = 3",
        ]
    )
    v = visitor.ScopedVisitor()
    mod = ast.parse(code)
    v.visit(mod)
    # T should not be among the refs or defs
    assert "out_of_scope" in v.refs
    assert "e" not in v.refs
    assert "f" not in v.refs
    assert "g" not in v.refs
    assert v.defs == set(["f", "v", "w", "x", "y", "z", "err", "err2", "err3"])


@pytest.mark.skipif("sys.version_info < (3, 11)")
def test_try_star_block() -> None:
    code = "\n".join(
        [
            "try:",
            (
                "  raise ExceptionGroup('eg', "
                "[ValueError(1), TypeError(2), OSError(3)])"
            ),
            "except* TypeError as e:",
            "  print(f'caught {type(e)} with nested {e.exceptions}')",
            "except* OSError as f:",
            "  print(f'caught {type(f)} with nested {f.exceptions}')",
            "else:",
            "  print('Type and Os not raised')",
            "finally:",
            "  print('finally')",
        ]
    )
    v = visitor.ScopedVisitor()
    mod = ast.parse(code)
    v.visit(mod)
    # T should not be among the refs or defs
    assert v.defs == set([])
    assert "e" not in v.refs
    assert "f" not in v.refs


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


def test_private_ref_requirement_caught() -> None:
    code = "\n".join(
        [
            "x = 1",
            "_x = 1",
            "def foo():",
            "  z = _x + x + X",
        ]
    )
    v = visitor.ScopedVisitor()
    mod = ast.parse(code)
    v.visit(mod)
    assert len(v.defs & set(["foo", "x"])) == 2
    assert len(v.defs - set(["foo", "x"])) == 1
    (private,) = v.defs - set(["foo", "x"])
    assert private.startswith("_")
    assert private.endswith("_x")
    assert v.refs == set(["X"])
    assert v.variable_data == {
        private: [VariableData(kind="variable")],
        "x": [VariableData(kind="variable")],
        "foo": [
            VariableData(kind="function", required_refs={"X", "x", private})
        ],
    }


def test_outer_ref_not_resolved_by_inner_resolution() -> None:
    code = cleandoc(
        """
        def f():
            x
            def g():
                def h():
                    x
                x = 0
        """
    )
    v = visitor.ScopedVisitor()
    mod = ast.parse(code)
    v.visit(mod)
    assert v.defs == {"f"}
    assert v.refs == {"x"}


def test_deleted_ref_basic() -> None:
    code = "del x"
    v = visitor.ScopedVisitor()
    mod = ast.parse(code)
    v.visit(mod)
    assert not v.defs
    assert v.refs == {"x"}
    assert v.deleted_refs == {"x"}


def test_not_deleted_ref() -> None:
    code = cleandoc(
        """
    x = 0
    def fn():
        if False:
            z = x
            del x
    x
    """
    )

    v = visitor.ScopedVisitor()
    mod = ast.parse(code)
    v.visit(mod)
    assert v.defs == {"x", "fn"}
    assert not v.refs
    assert not v.deleted_refs


@pytest.mark.xfail(reason="Unbound locals are currently treated as refs")
def test_unbound_local_not_deleted_ref() -> None:
    # here `x` is an unbound local, because
    # `del` adds `x` to scope. In particular,
    # `z = x` raises an UnboundLocalError, even
    # if `x` is in the global scope, meaning
    # that technically:
    #
    #   1. this code should not have any refs
    #   2. so del `x` is not deleting a ref
    code = cleandoc(
        """
    def fn():
        z = x
        del x
    """
    )

    v = visitor.ScopedVisitor()
    mod = ast.parse(code)
    v.visit(mod)
    assert v.defs == {"fn"}
    # TODO(akshayka): These assertions currently fail.
    assert not v.refs
    assert not v.deleted_refs


HAS_DEPS = DependencyManager.duckdb.has()


@pytest.mark.skipif(not HAS_DEPS, reason="Requires duckdb")
def test_sql_statement() -> None:
    code = "\n".join(
        [
            "df = mo.sql('select * from cars')",
        ]
    )
    v = visitor.ScopedVisitor()
    mod = ast.parse(code)
    v.visit(mod)
    assert v.defs == set(["df"])
    assert v.refs == set(["cars", "mo"])


@pytest.mark.skipif(not HAS_DEPS, reason="Requires duckdb")
def test_sql_statement_with_marimo_sql() -> None:
    code = "\n".join(
        [
            "df = marimo.sql('select * from cars')",
        ]
    )
    v = visitor.ScopedVisitor()
    mod = ast.parse(code)
    v.visit(mod)
    assert v.defs == set(["df"])
    assert v.refs == set(["cars", "marimo"])


@pytest.mark.skipif(not HAS_DEPS, reason="Requires duckdb")
@pytest.mark.parametrize(
    "code",
    [
        "df = duckdb.sql('select * from cars')",
        "df = duckdb.execute('select * from cars')",
    ],
)
def test_sql_statement_with_duckdb_sql(code: str) -> None:
    v = visitor.ScopedVisitor()
    mod = ast.parse(code)
    v.visit(mod)
    assert v.defs == set(["df"])
    assert v.refs == set(["cars", "duckdb"])


@pytest.mark.skipif(not HAS_DEPS, reason="Requires duckdb")
def test_sql_statement_with_f_string() -> None:
    code = "\n".join(
        [
            "df = mo.sql(f'select * from cars where name = {name}')",
        ]
    )
    v = visitor.ScopedVisitor()
    mod = ast.parse(code)
    v.visit(mod)
    assert v.defs == set(["df"])
    assert v.refs == set(["cars", "mo", "name"])


@pytest.mark.skipif(not HAS_DEPS, reason="Requires duckdb")
def test_sql_statement_with_rf_string() -> None:
    code = "\n".join(
        [
            "df = mo.sql(rf'select * from cars where name = {name}')",
        ]
    )
    v = visitor.ScopedVisitor()
    mod = ast.parse(code)
    v.visit(mod)
    assert v.defs == set(["df"])
    assert v.refs == set(["cars", "mo", "name"])


def test_print_f_string() -> None:
    import ast

    joined_str = ast.parse("f'select * from cars where name = {name}'")
    assert isinstance(joined_str.body[0].value, ast.JoinedStr)  # type: ignore
    assert (
        normalize_sql_f_string(joined_str.body[0].value)  # type: ignore
        == "select * from cars where name = null"
    )

    joined_str = ast.parse(
        "f'select * from \\'{table}\\' where name = {name}'"
    )
    assert isinstance(joined_str.body[0].value, ast.JoinedStr)  # type: ignore
    assert (
        normalize_sql_f_string(joined_str.body[0].value)  # type: ignore
        == "select * from 'null' where name = null"
    )


def test_normalize_sql_f_string_with_empty_quotes() -> None:
    import ast

    joined_str = ast.parse(
        "f'SELECT comment, REGEXP_REPLACE(comment, \\'*/.\\', \\'\\') regex_name,'"
    )
    assert isinstance(joined_str.body[0].value, ast.JoinedStr)  # type: ignore
    assert (
        normalize_sql_f_string(joined_str.body[0].value)
        == "SELECT comment, REGEXP_REPLACE(comment, '*/.', '') regex_name,"
    )  # type: ignore


@pytest.mark.skipif(not HAS_DEPS, reason="Requires duckdb")
def test_sql_empty_statement() -> None:
    code = "mo.sql('')"
    v = visitor.ScopedVisitor()
    mod = ast.parse(code)
    v.visit(mod)
    assert v.defs == set([])
    assert v.refs == set(["mo"])


@pytest.mark.skipif(not HAS_DEPS, reason="Requires duckdb")
def test_sql_empty_statement_duckdb() -> None:
    code = "duckdb.sql('')"
    v = visitor.ScopedVisitor()
    mod = ast.parse(code)
    v.visit(mod)
    assert v.defs == set([])
    assert v.refs == set(["duckdb"])


@pytest.mark.skipif(not HAS_DEPS, reason="Requires duckdb")
def test_sql_multiple_tables() -> None:
    code = "\n".join(
        [
            "df = mo.sql('select * from cars left join"
            " cars2 on cars.id = cars2.id')",
        ]
    )
    v = visitor.ScopedVisitor()
    mod = ast.parse(code)
    v.visit(mod)
    assert v.defs == set(["df"])
    assert v.refs == set(["cars", "cars2", "mo"])


@pytest.mark.skipif(not HAS_DEPS, reason="Requires duckdb")
def test_sql_from_another_module() -> None:
    code = "\n".join(
        [
            "df = lib.sql('select * from cars')",
        ]
    )
    v = visitor.ScopedVisitor()
    mod = ast.parse(code)
    v.visit(mod)
    assert v.defs == set(["df"])
    assert v.refs == set(["lib"])


@pytest.mark.skipif(not HAS_DEPS, reason="Requires duckdb")
def test_sql_statement_with_url() -> None:
    code = "\n".join(
        [
            'mo.sql("CREATE OR replace TABLE cars as '
            "FROM 'https://datasets.marimo.app/cars.csv';\")",
        ]
    )
    v = visitor.ScopedVisitor()
    mod = ast.parse(code)
    v.visit(mod)
    assert v.defs == set(["cars"])
    assert v.variable_data == {"cars": [VariableData("table")]}
    assert v.refs == set(["mo"])


@pytest.mark.skipif(not HAS_DEPS, reason="Requires duckdb")
def test_sql_statement_with_function() -> None:
    code = dedent('''
    prompt_embeddings = mo.sql(
        f"""
        SELECT *, embedding(text) as text_embedding
        FROM prompts;
        """
    )
    ''')
    v = visitor.ScopedVisitor()
    mod = ast.parse(code)
    v.visit(mod)
    assert v.defs == set(["prompt_embeddings"])
    assert v.refs == set(["mo", "prompts"])


@pytest.mark.skipif(not HAS_DEPS, reason="Requires duckdb")
def test_unparsable_sql_doesnt_fail() -> None:
    code = "\n".join(
        [
            # duckdb will raise a BinderError, but codegen shouldnt fail
            "df = mo.sql('select * from cars where cars.foo = ANY({bar})')",
        ]
    )
    v = visitor.ScopedVisitor()
    mod = ast.parse(code)
    v.visit(mod)
    assert v.defs == set(["df"])
    assert v.refs == set(["mo"])


@pytest.mark.skipif(not HAS_DEPS, reason="Requires duckdb")
def test_sql_attach() -> None:
    code = "\n".join(
        [
            "mo.sql(f\"ATTACH 'dbname=postgres user=postgres host=127.0.0.1 password=password' as db\")"  # noqa:E501
        ]
    )
    v = visitor.ScopedVisitor()
    mod = ast.parse(code)
    v.visit(mod)
    assert v.defs == set(["db"])
    assert v.refs == set(["mo"])


@pytest.mark.skipif(not HAS_DEPS, reason="Requires duckdb")
def test_sql_attach_f_string() -> None:
    code = "\n".join(
        [
            "mo.sql(f\"ATTACH 'dbname=postgres user=postgres host=127.0.0.1 password={PASSWORD}' as db\")"  # noqa:E501
        ]
    )
    v = visitor.ScopedVisitor()
    mod = ast.parse(code)
    v.visit(mod)
    assert v.defs == set(["db"])
    assert v.refs == set(["mo", "PASSWORD"])


@pytest.mark.skipif(not HAS_DEPS, reason="Requires duckdb")
def test_sql_int_f_string() -> None:
    code = "\n".join(["mo.sql(f'SELECT * FROM df LIMIT {lim}')"])
    v = visitor.ScopedVisitor()
    mod = ast.parse(code)
    v.visit(mod)
    assert not v.defs
    assert v.refs == set(["mo", "df", "lim"])


@pytest.mark.skipif(not HAS_DEPS, reason="Requires duckdb")
def test_sql_column_f_string() -> None:
    code = "\n".join(["mo.sql(f'SELECT {col} FROM df LIMIT {lim}')"])
    v = visitor.ScopedVisitor()
    mod = ast.parse(code)
    v.visit(mod)
    assert not v.defs
    assert v.refs == set(["mo", "df", "lim", "col"])


@pytest.mark.skipif(not HAS_DEPS, reason="Requires duckdb")
def test_sql_value_f_string() -> None:
    code = "\n".join(["mo.sql(f'SELECT * FROM df WHERE {col} = {val}')"])
    v = visitor.ScopedVisitor()
    mod = ast.parse(code)
    v.visit(mod)
    assert not v.defs
    assert v.refs == set(["mo", "df", "col", "val"])


@pytest.mark.skipif(not HAS_DEPS, reason="Requires duckdb")
def test_sql_table_f_string() -> None:
    code = "\n".join(["mo.sql(f'SELECT * FROM {my_table} LIMIT {lim}')"])
    v = visitor.ScopedVisitor()
    mod = ast.parse(code)
    v.visit(mod)
    assert not v.defs
    assert v.refs == set(["mo", "my_table", "lim"])
