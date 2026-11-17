# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from textwrap import dedent

import pytest

from marimo._ast.compiler import compile_cell
from marimo._types.ids import CellId_t

# Each cell binds a cell-level `_x` and reads a private name from a nested
# scope. Renaming must not change what the cell computes.
CASES = {
    "method_skips_class_attribute": """
        def outer():
            class C:
                _x = 0
                def value(self):
                    return _x
            _x = 10
            return C().value()
        result = outer()
    """,
    "except_target_in_enclosing_function": """
        _x = 10
        def outer():
            class C:
                _x = 0
                def value(self):
                    return _x
            try:
                raise ValueError(20)
            except ValueError as _x:
                return repr(C().value())
        result = outer()
    """,
    "except_target_unbound_after_handler": """
        _x = 10
        def outer():
            try:
                raise ValueError
            except ValueError as _x:
                pass
            try:
                return _x
            except UnboundLocalError:
                return "unbound"
        result = outer()
    """,
    "del_makes_name_local": """
        _x = 10
        def f():
            try:
                _x
            except UnboundLocalError:
                return "unbound"
            del _x
        result = f()
    """,
    "read_before_write_is_unbound": """
        _x = 10
        def f():
            try:
                y = _x
            except UnboundLocalError:
                y = "unbound"
            _x = 20
            return y
        result = f()
    """,
    "later_binding_in_enclosing_function": """
        _x = 10
        def outer():
            value = lambda: _x
            values = (_x for _ in (0,))
            def f():
                return _x
            _x = 20
            return (value(), next(values), f())
        result = outer()
    """,
    "augmented_and_annotated_bindings": """
        _x = "M"
        def outer():
            def f():
                return _x
            _x: str
            try:
                _x += "a"
            except UnboundLocalError:
                _x = "b"
            return f()
        result = outer()
    """,
    "global_store_in_function": """
        _x = 10
        def outer():
            global _x
            def f():
                return _x
            _x = 20
            return f()
        result = (outer(), _x)
    """,
    "global_store_in_class": """
        _x = 10
        class C:
            global _x
            _x = 20
        result = _x
    """,
    "global_except_target_deletes_cell_name": """
        _x = 10
        def outer():
            global _x
            try:
                raise ValueError
            except ValueError as _x:
                pass
        outer()
        try:
            result = _x
        except NameError:
            result = "deleted"
    """,
    "global_hides_enclosing_binding": """
        _x = 10
        def outer():
            _x = 20
            def mid():
                global _x
                def g():
                    return _x
                return g()
            return mid()
        result = outer()
    """,
    "class_nonlocal": """
        _x = 10
        def outer():
            _x = 20
            class C:
                nonlocal _x
                v = _x
                _x = 5
            return (C.v, _x)
        result = outer()
    """,
    "class_body_reads_cell_before_own_binding": """
        _x = 10
        def outer():
            _x = 20
            class C:
                before = _x
                _x = 0
                after = _x
                del _x
                deleted = _x
            return (C.before, C.after, C.deleted)
        result = outer()
    """,
    "class_annotation_hides_enclosing_function": """
        _x = 10
        def outer():
            _x = 20
            class C:
                _x: int
                v = _x
            return C.v
        result = outer()
    """,
    "annotation_reads_class_namespace_then_cell": """
        _x = 10
        def outer():
            _x = 20
            class C:
                _x = 0
                del _x
                def m(self, a: _x): pass
            class D:
                _x = 30
                _x: int
                def m(self, a: _x): pass
            return (C.m.__annotations__["a"], D.m.__annotations__["a"])
        result = outer()
    """,
    "annotation_honors_class_global": """
        _x = 10
        def outer():
            class C:
                global _x
                def m(self, a: _x): pass
                _x = 30
            _x = 20
            return (C.m.__annotations__["a"], _x)
        result = (outer(), _x)
    """,
    "comprehension_target_bound_later": """
        _x = 10
        def outer():
            try:
                return [w for _ in (0,) for w in (_x,) for _x in (1,)]
            except UnboundLocalError:
                return "unbound"
        result = outer()
    """,
    "walrus_in_comprehension_binds_function": """
        _x = 10
        def outer():
            def f():
                return _x
            [(_x := i) for i in (20,)]
            return f()
        result = outer()
    """,
    "binding_forms_in_function": """
        _x = 10
        def outer():
            def f():
                return _x
            import os as _x
            match 20:
                case _x:
                    pass
            for _x in (30,):
                pass
            return f()
        result = outer()
    """,
    "function_annotation": """
        _x = 10
        def outer():
            try:
                def f(a: _x): pass
            except UnboundLocalError:
                return "unbound"
            _x = 20
            return f.__annotations__["a"]
        result = outer()
    """,
    "future_annotations_resolve_in_cell_globals": """
        from __future__ import annotations
        import typing
        _x = int
        def outer():
            def f(a: _x): pass
            return typing.get_type_hints(f)["a"]
        result = outer()
    """,
    "unaliased_private_import": """
        from os import _exit
        def f():
            return _exit.__name__
        result = f()
    """,
    "type_alias_value": """
        _x = 10
        def outer():
            type A = _x
            _x = 20
            return A.__value__
        result = outer()
    """,
    "type_parameter_bound": """
        _x = 10
        def outer():
            def f[T: _x](): pass
            _x = 20
            return f.__type_params__[0].__bound__
        result = outer()
    """,
}


# A class body reads its own namespace and then the globals, so a read that
# can find either binding has no single correct renaming.
KNOWN_GAPS = {
    "class_conditional_store": """
        _x = 10
        class C:
            if False:
                _x = 0
            v = _x
        result = C.v
    """,
    "class_augmented_assignment": """
        _x = "a"
        class C:
            _x += "b"
        result = C._x
    """,
}


def _run(code: str, *, renamed: bool) -> object:
    namespace: dict[str, object] = {}
    try:
        if renamed:
            body = compile_cell(code, cell_id=CellId_t("0")).body
            assert body is not None
        else:
            body = compile(code, "<cell>", "exec", dont_inherit=True)
        exec(body, namespace)
    except Exception as error:
        return f"raised {type(error).__name__}"
    return namespace["result"]


@pytest.mark.parametrize("source", CASES.values(), ids=CASES.keys())
def test_private_name_resolves_like_python(source: str) -> None:
    code = dedent(source)
    try:
        compile(code, "<cell>", "exec", dont_inherit=True)
    except SyntaxError:
        pytest.skip("syntax needs a newer Python")
    expected = _run(code, renamed=False)
    assert not str(expected).startswith("raised"), expected
    assert _run(code, renamed=True) == expected


@pytest.mark.xfail(strict=True, reason="no static renaming is correct")
@pytest.mark.parametrize("source", KNOWN_GAPS.values(), ids=KNOWN_GAPS.keys())
def test_class_namespace_fallback_is_a_known_gap(source: str) -> None:
    code = dedent(source)
    assert _run(code, renamed=True) == _run(code, renamed=False)
