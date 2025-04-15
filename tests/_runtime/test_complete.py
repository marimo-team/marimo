from __future__ import annotations

from marimo._runtime.complete import _build_docstring_cached
from tests.mocks import snapshotter

snapshot = snapshotter(__file__)


def test_build_docstring_function_no_init():
    result = _build_docstring_cached(
        completion_type="function",
        completion_name="my_func",
        signature_strings=("my_func(arg1, arg2)",),
        raw_body="This is a simple docstring for a function.",
        init_docstring=None,
    )
    assert "my_func" in result
    assert "This is a simple docstring for a function." in result
    assert '<div class="codehilite">' in result
    snapshot("docstrings_function.txt", result)


def test_docstring_function_with_google_style():
    result = _build_docstring_cached(
        completion_type="function",
        completion_name="my_func",
        signature_strings=("my_func(arg1, arg2)",),
        raw_body="""
        Args:
            arg1: Description of arg1.
            arg2: Description of arg2.

        Returns:
            HTML: A description of the return value.
        """,
        init_docstring=None,
    )

    assert "Description of arg1" in result
    assert "Description of arg2" in result
    assert "A description of the return value" in result
    snapshot("docstrings_function_google.txt", result)


def test_build_docstring_class_with_init():
    result = _build_docstring_cached(
        completion_type="class",
        completion_name="MyClass",
        signature_strings=("MyClass()",),
        raw_body="Some docstring for the class.",
        init_docstring="__init__ docstring:\n\nClass init details.",
    )
    assert "MyClass" in result
    assert "Some docstring for the class." in result
    assert "Class init details." in result
    snapshot("docstrings_class.txt", result)


def test_build_docstring_module():
    result = _build_docstring_cached(
        completion_type="module",
        completion_name="os",
        signature_strings=(),
        raw_body=None,
        init_docstring=None,
    )
    assert "module os" in result
    assert "```python3" not in result
    snapshot("docstrings_module.txt", result)


def test_build_docstring_keyword():
    result = _build_docstring_cached(
        completion_type="keyword",
        completion_name="yield",
        signature_strings=(),
        raw_body=None,
        init_docstring=None,
    )
    assert "keyword yield" in result
    assert "```python3" not in result
    snapshot("docstrings_keyword.txt", result)


def test_build_docstring_no_signature_no_body():
    result = _build_docstring_cached(
        completion_type="statement",
        completion_name="random_statement",
        signature_strings=(),
        raw_body=None,
        init_docstring=None,
    )
    assert len(result.strip()) == 0
