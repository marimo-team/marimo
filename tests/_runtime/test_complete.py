from __future__ import annotations

import random
import threading
from collections.abc import Mapping
from inspect import signature
from types import ModuleType
from typing import Any
from unittest import mock

import jedi
import pytest

import marimo
from marimo._dependencies.dependencies import DependencyManager
from marimo._messaging.ops import CompletionResult
from marimo._messaging.types import KernelMessage, Stream
from marimo._runtime.complete import (
    _build_docstring_cached,
    _maybe_get_key_options,
    _resolve_chained_key_path,
    complete,
)
from marimo._runtime.patches import patch_jedi_parameter_completion
from marimo._runtime.requests import CodeCompletionRequest
from marimo._types.ids import CellId_t
from tests.mocks import snapshotter

snapshot = snapshotter(__file__)
HAS_PANDAS = DependencyManager.pandas.has()


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
    assert '<div class="language-python3 codehilite">' in result
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
    del arg1, arg2


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
def test_parameter_descriptions(obj: Any, runtime_inference: bool):
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
    if path.endswith("dummy_func"):
        pytest.skip("Not picking up parameters for dummy_func")
    if path.endswith("ChatMessage"):
        pytest.skip(
            "ChatMessage is a msgspec struct which does not support Jedi dict completions"
        )
    call = f"{path}("
    code = f"import {import_name};{call}"
    jedi.settings.auto_import_modules = ["marimo"] if runtime_inference else []
    script = jedi.Script(code=code)
    completions: list[Any] = script.complete(line=1, column=len(code))
    param_completions: dict[str, Any] = {
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
            f"Jedi did not suggest {param_name} in {call}. It suggested {param_completions.keys()}"
        )
        jedi_param = param_completions[param_name]
        docstring = jedi_param.docstring()
        assert docstring != "", f"Empty docstring result: {call}{param_name}"
        assert "NoneType" not in docstring, (
            f"NoneType found in docstring: {call}{param_name}"
        )


DOCUMENT_AND_EXPECTS_COMPLETIONS: tuple[tuple[str, bool], ...] = (
    ("obj['", True),
    ('obj["', True),
    ("assigned = obj['", True),
    ("multiline = 'foo'\nobj['", True),
    ("for i in iterator:\n\tobj['", True),
    # shouldn't trigger on the following notations
    ("obj.", False),
    ("obj", False),
)


def cases_objects_supporting_key_completion() -> tuple[
    tuple[Any, list[str]], ...
]:
    """Values stored in `globals` when key completion is triggered."""

    class IPythonImplemented:
        def __init__(self):
            self._table = {
                "foo": [0, 1],
                "bar": [1.0, 3.0],
            }

        @property
        def a_property(self) -> str:
            """This is a property"""
            return "prop value"

        def __getitem__(self, key: str) -> list:
            """Returns a mock column"""
            return self._table[key]

        def _ipython_key_completions_(self) -> list[str]:
            return list(self._table.keys())

    class CustomMapping(Mapping):
        def __init__(self):
            self._data = {
                "foo": [0, 1],
                "bar": [1.0, 3.0],
            }

        def __iter__(self):
            return iter(self._data.keys())

        def __getitem__(self, key):
            raise NotImplementedError

        def __len__(self):
            raise NotImplementedError

    static_key_dict = ({"foo": [0, 1], "bar": [1.0, 3.0]}, ["foo", "bar"])
    # use different ranges to prevent key collisions
    dynamic_key_1 = str(random.randint(0, 9))
    dynamic_key_2 = str(random.randint(10, 19))
    dynamic_key_dict = (
        {dynamic_key_1: "val1", dynamic_key_2: "val2"},
        [dynamic_key_1, dynamic_key_2],
    )
    mixed_keys_dict = (
        {"foo": [0, 1], dynamic_key_1: "val2"},
        ["foo", dynamic_key_1],
    )
    ipython_case = (IPythonImplemented(), ["foo", "bar"])
    custom_mapping_case = (CustomMapping(), ["foo", "bar"])

    return (
        static_key_dict,
        dynamic_key_dict,
        mixed_keys_dict,
        ipython_case,
        custom_mapping_case,
    )


@pytest.mark.parametrize(
    "document_and_expects_completions", DOCUMENT_AND_EXPECTS_COMPLETIONS
)
@pytest.mark.parametrize(
    "obj_and_expected_completions", cases_objects_supporting_key_completion()
)
def test_maybe_get_key_options(
    document_and_expects_completions: tuple[str, bool],
    obj_and_expected_completions: tuple[Any, list[str]],
):
    """Low-level test for `_maybe_get_key_options()`"""
    document, expects_completions = document_and_expects_completions
    obj, expected_completions = obj_and_expected_completions
    glbls = {"obj": obj, "other": 10}
    lock = threading.RLock()
    script = jedi.Script(code=document)

    completions = _maybe_get_key_options(
        document=document, script=script, glbls=glbls, glbls_lock=lock
    )

    if expects_completions is True:
        assert [c.name for c in completions] == expected_completions
    else:
        assert completions == []


# TODO case could be added to `cases_objects_supporting_key_completions()`
# the test has the same logic of `test_maybe_get_key_options()`
@pytest.mark.skipif(not HAS_PANDAS, reason="pandas not installed.")
@pytest.mark.parametrize(
    "document_and_expects_completions", DOCUMENT_AND_EXPECTS_COMPLETIONS
)
def test_maybe_get_key_options_pandas_dataframe(
    document_and_expects_completions: tuple[str, bool],
) -> None:
    import pandas as pd

    document, expects_completions = document_and_expects_completions
    expected_completions = ["foo", "bar"]
    glbls = {
        "obj": pd.DataFrame({"foo": [0, 1], "bar": [9.0, 2.0]}),
        "other": 10,
    }
    lock = threading.RLock()
    script = jedi.Script(code=document)

    completions = _maybe_get_key_options(
        document=document,
        script=script,
        glbls=glbls,
        glbls_lock=lock,
    )

    if expects_completions is True:
        assert [c.name for c in completions] == expected_completions
    else:
        assert completions == []


class CaptureStream(Stream):
    def __init__(self):
        self.messages: list[KernelMessage] = []

    def write(self, data: KernelMessage) -> None:
        self.messages.append(data)

    @property
    def operations(self) -> list[dict[str, Any]]:
        import json

        return [json.loads(op_data) for op_data in self.messages]


# TODO add test cases for all other completion modalities
# TODO improve coupling between variable name, source code, and assertions
@pytest.mark.parametrize(
    "document_and_expects_completions", DOCUMENT_AND_EXPECTS_COMPLETIONS
)
@pytest.mark.parametrize(
    "object_name", ["static_key", "dynamic_key", "mixed_keys", "ipython_data"]
)
@pytest.mark.parametrize("chained_completion", [True, False])
def test_key_completion_main_entrypoint(
    document_and_expects_completions: tuple[str, bool],
    object_name: str,
    chained_completion: bool,
) -> None:
    """Test key completion using the main entrypoint `marimo._runtime.complete()`

    Params:
        document_and_expects_completions: contains (`document`, `expects_completion`)
            `document` is the source code up to the cursor when triggering autocompletion.
            `expects_completions` is a boolean whether we expect key completion; if False,
            it could still trigger other completion mechanisms
        object_name: the name of the object in the source code that we'll assign to `obj`.
            All tests parametrization trigger completion on `obj`, but we change what
            `obj` points.
        chained_completion: if False, `obj = object_name`. If True, `obj = {top_level_key: object_name}`
            This allows to nested chained autocompletion.
    """
    top_level_key = "depth0"
    document, expects_key_completion = document_and_expects_completions
    if chained_completion:
        document = document.replace("obj[", f"obj['{top_level_key}'][")

    other_cells_code = '''\
import random

class CustomData:
    def __init__(self):
        self._table = {
            "foo": [0, 1],
            "bar": [1., 3.],
            "baz": [True, True],
        }

    @property
    def a_property(self) -> str:
        """This is a property"""
        return "prop value"

    def __getitem__(self, key: str) -> list:
        """Returns a mock column"""
        return self._table[key]

    def _ipython_key_completions_(self) -> list[str]:
        return list(self._table.keys())

ipython_data = CustomData()
static_key = {"static_key": "foo"}
dynamic_key = {str(random.randint(0, 10)): "foo"}
mixed_keys = {"static_key": "foo", str(random.randint(0, 10)): "bar"}
'''
    if chained_completion:
        other_cells_code += f"obj = dict({top_level_key}={object_name})"
    else:
        other_cells_code += f"obj = {object_name}"

    mock_other_cell = mock.MagicMock()
    mock_other_cell.code = other_cells_code

    mock_current_cell = mock.MagicMock()
    mock_current_cell.code = document
    current_cell_id = CellId_t("my-request-id")

    mock_graph = mock.MagicMock()
    mock_graph.cells = {
        "other-cell-id": mock_other_cell,
        current_cell_id: mock_current_cell,
    }

    glbls = {}
    exec(other_cells_code, {}, glbls)
    # check existence of variables in globals and their type
    assert isinstance(
        glbls.get("ipython_data"), glbls.get("CustomData", Exception)
    )
    assert isinstance(glbls.get("static_key"), dict)
    assert isinstance(glbls.get("dynamic_key"), dict)
    assert isinstance(glbls.get("mixed_keys"), dict)

    lock = threading.RLock()
    local_stream = CaptureStream()

    completion_request = CodeCompletionRequest(
        id="request_id",
        document=document,
        cell_id=current_cell_id,
    )

    complete(
        request=completion_request,
        graph=mock_graph,
        glbls=glbls,
        glbls_lock=lock,
        stream=local_stream,
    )

    message_name = local_stream.operations[0]["op"]
    content = local_stream.operations[0]
    prefix_length = content["prefix_length"]
    options = content["options"]
    options_values = [option["name"] for option in options]

    assert len(local_stream.messages) == 1
    assert message_name == CompletionResult.name
    # TODO if `expects_completions=False`, something else than `_maybe_get_key_options()`
    # could be returning values
    if expects_key_completion is False:
        return

    assert prefix_length == 0
    assert all(option["type"] == "property" for option in options)
    assert all(option["completion_info"] == "key" for option in options)

    expected_keys: list[str] = []
    if object_name == "static_key":
        # from source code in variable `other_cells_code`
        expected_keys = ["static_key"]
    elif object_name == "dynamic_key":
        expected_keys = list(glbls["dynamic_key"].keys())
    elif object_name == "mixed_keys":
        expected_keys = list(glbls["mixed_keys"].keys())
    elif object_name == "ipython_data":
        # from source code in variable `other_cells_code`
        expected_keys = ["foo", "bar", "baz"]
    else:
        RuntimeError(
            f"Make sure you defined `expected_keys` for `{object_name}`"
            " Currently, the test is improperly defined."
        )

    # check `len()` to ensure `set()` operation doesn't deduplicate keys
    assert len(options_values) == len(expected_keys)
    assert set(options_values) == set(expected_keys)


@pytest.mark.parametrize(
    ("trigger_code", "expected_key_path"),
    # NOTE trigger code produce by marimo must end with `['` or `["`
    [
        ("obj['", []),
        ("obj['foo']['", [["foo"]]),
        ("obj['foo', 'bar']['", [["foo", "bar"]]),
        ("obj['foo']['bar']['", [["foo"], ["bar"]]),
    ],
)
def test_resolve_chained_key_path(
    trigger_code: str, expected_key_path: list[str]
) -> None:
    key_path = _resolve_chained_key_path("obj", trigger_code)
    assert key_path == expected_key_path
