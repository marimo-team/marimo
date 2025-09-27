# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass

from marimo._plugins.stateless.inspect import inspect


class SimpleClass:
    """A simple test class."""

    def __init__(self):
        self.value = 42
        self._private = "hidden"
        self.__dunder = "very hidden"

    def method(self):
        """A public method."""
        pass

    def _private_method(self):
        """A private method."""
        pass


def simple_function(x: int, y: str = "default") -> str:
    """A simple test function."""
    return f"{x} - {y}"


def test_inspect_basic_object() -> None:
    obj = SimpleClass()
    result = inspect(obj)
    html = result.text

    assert "instance" in html
    assert "SimpleClass" in html
    assert "42" in html
    assert "<div" in html
    assert "style=" in html


def test_inspect_with_docstring() -> None:
    result = inspect(SimpleClass)
    html = result.text
    assert "A simple test class" in html


def test_inspect_function() -> None:
    result = inspect(simple_function)
    html = result.text

    assert "function" in html
    assert "simple_function" in html
    # The signature may have HTML-escaped quotes or formatted differently
    assert "x:" in html
    assert "int" in html
    assert "y:" in html
    assert "str" in html


def test_inspect_with_methods() -> None:
    obj = SimpleClass()
    result = inspect(obj, methods=True)
    html = result.text
    assert "method" in html


def test_inspect_with_private() -> None:
    obj = SimpleClass()
    result = inspect(obj, private=True)
    html = result.text
    assert "_private" in html


def test_inspect_with_dunder() -> None:
    obj = SimpleClass()
    result = inspect(obj, dunder=True)
    html_str = result.text
    assert "_SimpleClass__dunder" in html_str or "__" in html_str

    result_with_all = inspect(obj, all=True)
    html_with_all = result_with_all.text
    assert "_SimpleClass__dunder" in html_with_all or "__" in html_with_all


def test_inspect_string_value() -> None:
    # When inspecting a string directly, it shows as an instance of str
    result = inspect("test string", value=True)
    html = result.text
    assert "test string" in html
    assert "instance" in html
    assert "str" in html

    # String coloring is used when strings appear in attributes
    class WithString:
        def __init__(self):
            self.text = "colored string"

    result2 = inspect(WithString())
    html2 = result2.text
    assert "light-dark(#cb4b16, #dc9656)" in html2


def test_inspect_dict() -> None:
    test_dict = {"key": "value", "number": 42}
    result = inspect(test_dict)
    html = result.text
    assert "dict" in html.lower() or "instance" in html


def test_inspect_list() -> None:
    test_list = [1, 2, 3, "test"]
    result = inspect(test_list)
    html = result.text
    assert "list" in html.lower() or "instance" in html


def test_inspect_module() -> None:
    import os

    result = inspect(os, methods=False)
    html = result.text
    assert "module" in html
    assert "os" in html


def test_inspect_html_escaping() -> None:
    class HTMLTest:
        def __init__(self):
            self.value = "<script>alert('xss')</script>"

    obj = HTMLTest()
    result = inspect(obj)
    html = result.text

    assert "&lt;script&gt;" in html or "&lt;" in html
    assert "<script>alert" not in html


def test_inspect_no_value() -> None:
    obj = SimpleClass()
    result = inspect(obj, value=False)
    html = result.text
    assert "<div" in html


def test_inspect_css_variables() -> None:
    result = inspect(SimpleClass())
    html = result.text

    assert "var(--" in html
    assert any(
        var in html
        for var in [
            "var(--slate-",
            "var(--background)",
            "var(--foreground)",
            "var(--blue-",
            "var(--green-",
            "var(--purple-",
        ]
    )


def test_inspect_type_pills() -> None:
    class_result = inspect(SimpleClass)
    assert "var(--blue-" in class_result.text

    func_result = inspect(simple_function)
    assert "var(--green-" in func_result.text

    instance_result = inspect(SimpleClass())
    assert "var(--crimson-" in instance_result.text

    import os

    module_result = inspect(os)
    assert "var(--orange-" in module_result.text


def test_inspect_divider() -> None:
    result = inspect(SimpleClass(), value=True)
    html = result.text
    # Check for the divider (could be single or double quotes)
    assert "height: 1px;" in html
    assert "var(--slate-3)" in html


def test_inspect_sort_attributes() -> None:
    class UnsortedClass:
        def __init__(self):
            self.zebra = 1
            self.apple = 2
            self.middle = 3

    obj = UnsortedClass()

    sorted_result = inspect(obj, sort=True)
    sorted_html = sorted_result.text

    unsorted_result = inspect(obj, sort=False)
    unsorted_html = unsorted_result.text

    for attr in ["zebra", "apple", "middle"]:
        assert attr in sorted_html
        assert attr in unsorted_html

    assert "<table" in sorted_html
    assert "<table" in unsorted_html


def test_inspect_repr_md() -> None:
    @dataclass
    class Value:
        value: str

    result = inspect(Value(value="one"))
    md = result._repr_md_()
    assert md == repr(Value(value="one"))


def test_inspect_repr_md_error() -> None:
    class ReprError:
        def __repr__(self):
            raise Exception("repr error")  # noqa: TRY002

    result = inspect(ReprError())
    md = result._repr_md_()
    assert "<div" in md
