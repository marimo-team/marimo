from __future__ import annotations

from inspect import signature
from types import ModuleType

import jedi
import pytest

import marimo
from marimo._dependencies.dependencies import DependencyManager
from marimo._runtime.complete import _build_docstring_cached
from marimo._runtime.patches import patch_jedi_parameter_completion
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
    if DependencyManager.docstring_to_markdown.has():
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
    if DependencyManager.docstring_to_markdown.has():
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


def collect_modules_to_check():
    top_level_modules_to_check = [marimo]
    submodules_to_check = []

    # Collect all public exported sub-modules
    for module in top_level_modules_to_check:
        for attribute in dir(module):
            if attribute.startswith("_"):
                continue
            candidate = getattr(module, attribute)
            if isinstance(candidate, ModuleType):
                submodules_to_check.append(candidate)

    return top_level_modules_to_check + submodules_to_check


def collect_functions_to_check():
    modules_to_check = collect_modules_to_check()
    assert len(modules_to_check) > 1
    objects_to_check = set()
    for module in modules_to_check:
        for attribute in dir(module):
            if attribute.startswith("_"):
                continue
            obj = getattr(module, attribute)
            if not callable(obj):
                continue
            objects_to_check.add(obj)
    assert len(objects_to_check) > 1
    return objects_to_check


def dummy_func(arg1: str, arg2: str) -> None:
    """
    Parameters
    ----------
    arg1
        polars often uses this format
    arg2 : str, required
        while other libraries prefer this format (which polars uses too)
    """


@pytest.mark.skipif(
    not DependencyManager.docstring_to_markdown.has(),
    reason="docstring_to_markdown is not installed",
)
@pytest.mark.parametrize(
    ("obj", "runtime_inference"),
    [[obj, False] for obj in collect_functions_to_check()]
    + [
        # Test runtime inference for a subset of values
        [marimo.accordion, True],
        [dummy_func, False],
    ],
    ids=lambda obj: f"{obj}"
    if isinstance(obj, bool)
    else f"{obj.__module__}.{obj.__qualname__}",
)
def test_parameter_descriptions(obj, runtime_inference):
    patch_jedi_parameter_completion()
    import_name = obj.__module__
    marimo_export = obj.__name__
    path = f"{import_name}.{marimo_export}"
    if path == "marimo._output.hypertext.Html":
        pytest.skip("Known issue with `Html` being a quasi-dataclass")
    if path.startswith("marimo._save.save."):
        pytest.skip(
            "Cache functions use overloads to distinguish calls and context managers"
            " this can be fixed by splitting docstring on per-oveload basis, but that"
            " is not yet supported by mkdocstrings for documentation rendering, see"
            " https://github.com/mkdocstrings/python/issues/135"
        )
    call = f"{path}("
    code = f"import {import_name};{call}"
    jedi.settings.auto_import_modules = ["marimo"] if runtime_inference else []
    script = jedi.Script(code=code)
    completions = script.complete(line=1, column=len(code))
    param_completions = {
        completion.name[:-1]: completion
        for completion in completions
        if completion.name.endswith("=")
    }
    for param_name, param in signature(obj).parameters.items():
        if param_name.startswith("_"):
            continue
        if param.kind in {param.VAR_KEYWORD, param.VAR_POSITIONAL}:
            continue
        assert param_name in param_completions, (
            f"Jedi did not suggest {param_name} in {call}"
        )
        jedi_param = param_completions[param_name]
        docstring = jedi_param.docstring()
        assert docstring != "", f"Empty docstring result: {call}{param_name}"
        assert "NoneType" not in docstring, (
            f"NoneType found in docstring: {call}{param_name}"
        )
