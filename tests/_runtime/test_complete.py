from __future__ import annotations

import random
import threading
import time
from collections.abc import Mapping
from inspect import signature
from types import ModuleType
from typing import Any
from unittest import mock

import jedi
import pytest

import marimo
from marimo._dependencies.dependencies import DependencyManager
from marimo._messaging.notification import CompletionResultNotification
from marimo._messaging.serde import deserialize_kernel_message
from marimo._messaging.types import KernelMessage, Stream
from marimo._runtime.commands import CodeCompletionCommand
from marimo._runtime.complete import (
    _build_docstring_cached,
    _get_completion_info,
    _get_completion_option,
    _get_completion_options,
    _get_completions,
    _get_docstring,
    _maybe_get_key_options,
    _resolve_chained_key_path,
    complete,
)
from marimo._runtime.patches import patch_jedi_parameter_completion
from marimo._types.ids import CellId_t
from tests.mocks import snapshotter

snapshot = snapshotter(__file__)
HAS_PANDAS = DependencyManager.pandas.has()
HAS_POLARS = DependencyManager.polars.has()


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
        signature_strings=("my_func(arg1: str, arg2: int)",),
        raw_body="""
        Args:
            arg1: Description of arg1.
            arg2: Description of arg2.

        Returns:
            HTML: A description of the return value.
        """,
        init_docstring=None,
        param_types=(("arg1", "str"), ("arg2", "int")),
    )

    assert "Description of arg1" in result
    assert "Description of arg2" in result
    assert "A description of the return value" in result
    assert "<code>str</code>" in result
    assert "<code>int</code>" in result
    snapshot("docstrings_function_google.txt", result)


def test_docstring_function_with_google_style_infers_types_from_jedi() -> None:
    patch_jedi_parameter_completion()

    code = '''def func(arg: int) -> None:
    """Do something

    Args:
        arg: An integer argument
    """
    return

func'''
    script = jedi.Script(code)
    completions = script.complete(line=9, column=4)
    func_completion = next(c for c in completions if c.name == "func")
    result = _get_docstring(func_completion)

    assert "<code>int</code>" in result
    assert "An integer argument" in result


def test_docstring_function_infers_varargs_types_from_jedi() -> None:
    patch_jedi_parameter_completion()

    code = '''def func(*args: str, **kwargs: float) -> None:
    """Do something

    Args:
        *args: extra positionals
        **kwargs: extra keywords
    """
    return

func'''
    script = jedi.Script(code)
    completions = script.complete(line=10, column=4)
    func_completion = next(c for c in completions if c.name == "func")
    result = _get_docstring(func_completion)

    assert "extra positionals" in result
    assert "extra keywords" in result
    # Jedi reports varargs as container types (`args`/`kwargs` without stars);
    # they should still populate the `*args`/`**kwargs` rows.
    assert "<code>Tuple[str]</code>" in result
    assert "<code>Dict[str, float]</code>" in result


def test_docstring_math_directive_is_normalized():
    result = _build_docstring_cached(
        completion_type="function",
        completion_name="my_func",
        signature_strings=("my_func(arg1)",),
        raw_body=r"""
        For :math:`t > 0`, we have:

        .. math::

            m_t = \beta_1 \cdot m_{t-1}
        """,
        init_docstring=None,
    )

    assert ".. math::" not in result
    assert ":math:`" not in result
    assert "<marimo-tex" in result
    assert "m_t" in result


def test_docstring_inline_math_directive_is_normalized():
    result = _build_docstring_cached(
        completion_type="function",
        completion_name="my_func",
        signature_strings=("my_func(arg1)",),
        raw_body=(
            r".. math::\begin{align*} m_t &= \beta_1 g_t "
            r"\\ v_t &= \beta_2 g_t^2 \end{align*}"
        ),
        init_docstring=None,
    )

    assert ".. math::" not in result
    assert "<marimo-tex" in result
    assert r"\begin{align*}" in result


def test_docstring_unindented_math_block_is_normalized():
    result = _build_docstring_cached(
        completion_type="function",
        completion_name="my_func",
        signature_strings=("my_func(arg1)",),
        raw_body=r"""
        .. math::

        \begin{align*}
        m_t &= \beta_1 g_t
        \end{align*}
        """,
        init_docstring=None,
    )

    assert ".. math::" not in result
    assert "<marimo-tex" in result
    assert r"\begin{align*}" in result


def test_docstring_inline_math_role_is_normalized():
    result = _build_docstring_cached(
        completion_type="function",
        completion_name="my_func",
        signature_strings=("my_func(arg1)",),
        raw_body=r"""Computes :math:`\alpha + \beta`.""",
        init_docstring=None,
    )

    assert ":math:`" not in result
    assert "<marimo-tex" in result
    assert r"\alpha + \beta" in result


def test_docstring_latex_delimiters_are_normalized():
    result = _build_docstring_cached(
        completion_type="function",
        completion_name="my_func",
        signature_strings=("my_func(arg1)",),
        raw_body=r"""Inline \(x^2\), display \[x^2 + y^2\], and $z^2$.""",
        init_docstring=None,
    )

    assert r"\(" not in result
    assert r"\[" not in result
    assert "<marimo-tex" in result
    assert result.count("<marimo-tex") >= 3


def test_docstring_math_normalization_skips_fenced_code_blocks():
    raw_docstring = """
Before

```python
formula = ":math:`x`"
directive = '''
.. math::

    x^2
'''
```

After :math:`y`
"""
    result = _build_docstring_cached(
        completion_type="function",
        completion_name="my_func",
        signature_strings=("my_func(arg1)",),
        raw_body=raw_docstring,
        init_docstring=None,
    )

    if DependencyManager.docstring_to_markdown.has():
        # docstring_to_markdown may normalize fenced code content to $$.
        assert "$$" in result
    else:
        assert ".. math::" in result
    assert ":math:`y`" not in result
    assert result.count("<marimo-tex") == 1


def test_get_docstring_class_init_uses_same_math_rendering_path():
    class _FakeSignature:
        def to_string(self) -> str:
            return "MyClass()"

    class _FakeInit:
        name = "__init__"

        def docstring(self, raw: bool = False) -> str:
            assert raw
            return r"""
            .. math::

                m_t = \beta_1 \cdot g_t
            """

    class _FakeDefinition:
        def defined_names(self) -> list[_FakeInit]:
            return [_FakeInit()]

    class _FakeCompletion:
        type = "class"
        name = "MyClass"

        def docstring(self, raw: bool = False) -> str:
            assert raw
            return "Class docs."

        def get_signatures(self) -> list[_FakeSignature]:
            return [_FakeSignature()]

        def goto(self) -> list[_FakeDefinition]:
            return [_FakeDefinition()]

    with mock.patch(
        "marimo._runtime.complete.jedi.api.classes.Name", _FakeDefinition
    ):
        result = _get_docstring(_FakeCompletion())

    assert "__init__ docstring:" in result
    assert ".. math::" not in result
    assert "<marimo-tex" in result


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
    return sorted(
        objects_to_check,
        key=lambda obj: f"{obj.__module__}.{obj.__qualname__}",
    )


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
    ids=lambda obj: (
        f"{obj}"
        if isinstance(obj, bool)
        else f"{obj.__module__}.{obj.__qualname__}"
    ),
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
            " this can be fixed by splitting docstring on per-overload basis, but that"
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
        # raw=True: Jedi otherwise prepends inferred signature strings for
        # annotated unions like str|None / int|None (builtin ctor docs + NoneType),
        # which is noise for dataclass field comments served by py__doc__.
        docstring = jedi_param.docstring(raw=True)
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
        # Attempt to deserialize the message to ensure it is valid
        deserialize_kernel_message(data)

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

    completion_request = CodeCompletionCommand(
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
    assert message_name == CompletionResultNotification.name
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
        raise RuntimeError(
            f"Make sure you defined `expected_keys` for `{object_name}`"
            " Currently, the test is improperly defined."
        )

    # check `len()` to ensure `set()` operation doesn't deduplicate keys
    assert len(options_values) == len(expected_keys)
    assert set(options_values) == set(expected_keys)


def _run_complete(document: str, other_code: str = "") -> dict[str, Any]:
    """Run the `complete()` entrypoint and return the emitted notification."""
    current_cell_id = CellId_t("current-cell")

    mock_other_cell = mock.MagicMock()
    mock_other_cell.code = other_code
    mock_current_cell = mock.MagicMock()
    mock_current_cell.code = document

    mock_graph = mock.MagicMock()
    mock_graph.cells = {
        "other-cell": mock_other_cell,
        current_cell_id: mock_current_cell,
    }

    glbls: dict[str, Any] = {}
    if other_code:
        exec(other_code, {}, glbls)

    stream = CaptureStream()
    complete(
        request=CodeCompletionCommand(
            id="request-id", document=document, cell_id=current_cell_id
        ),
        graph=mock_graph,
        glbls=glbls,
        glbls_lock=threading.RLock(),
        stream=stream,
    )
    assert len(stream.operations) == 1
    return stream.operations[0]


@pytest.mark.parametrize("document", ["1,", "foo(", "foo(1,", "[1, "])
def test_no_completions_after_comma_or_paren_without_signature(
    document: str,
) -> None:
    """An empty prefix after `,` or `(` must not dump the whole namespace.

    Regression test: previously `,` and `(` were treated as completion trigger
    characters, so typing e.g. `1,` opened a popup listing every builtin.
    """
    content = _run_complete(document)
    assert content["op"] == CompletionResultNotification.name
    assert content["options"] == []


@pytest.mark.parametrize("document", ["my_func(", "my_func(1,"])
def test_signature_shown_after_comma_or_paren_in_call(document: str) -> None:
    """Inside a known call, an empty prefix falls through to signature help."""
    content = _run_complete(
        document, other_code="def my_func(a, b): return a + b"
    )
    assert content["op"] == CompletionResultNotification.name
    assert len(content["options"]) == 1
    option = content["options"][0]
    assert option["type"] == "tooltip"
    assert option["name"] == "my_func"


@pytest.mark.parametrize("document", ["1 / ", "x = 10 /", "a = b / "])
def test_no_completions_for_division_operator(document: str) -> None:
    """`/` triggers path completion inside strings, but as a division operator
    it must not dump the whole namespace.
    """
    content = _run_complete(document)
    assert content["op"] == CompletionResultNotification.name
    assert content["options"] == []


@pytest.mark.parametrize(
    "document",
    [
        "from dataclasses import ",
        "from dataclasses import field, ",
        "from  dataclasses  import  ",
    ],
)
def test_completion_after_from_import_with_empty_prefix(document: str) -> None:
    """`from module import <cursor>` must complete on an empty prefix.

    Regression test for #10140: Jedi returns the module's importable names here,
    but an empty prefix that isn't a `.`/`/` trigger was being discarded, so the
    popup never opened after `from x import `.
    """
    content = _run_complete(document)
    assert content["op"] == CompletionResultNotification.name
    assert content["prefix_length"] == 0
    names = {option["name"] for option in content["options"]}
    assert {"dataclass", "field", "asdict"} <= names


def test_completion_after_bare_import_with_empty_prefix() -> None:
    """`import <cursor>` completes to top-level modules on an empty prefix."""
    content = _run_complete("import ")
    assert content["op"] == CompletionResultNotification.name
    assert content["prefix_length"] == 0
    names = {option["name"] for option in content["options"]}
    assert "dataclasses" in names


def test_path_completion_still_works(tmp_path: Any) -> None:
    """`/` still triggers file-path completion inside a string literal."""
    (tmp_path / "marimo_data.csv").write_text("x\n")
    content = _run_complete(f'open("{tmp_path}/')
    assert content["options"]
    assert all(option["type"] == "path" for option in content["options"])
    assert any(
        "marimo_data.csv" in option["name"] for option in content["options"]
    )


def test_parameter_completion_omits_full_function_docstring() -> None:
    """Completing a parameter must not dump the whole function docstring.

    Regression test: `param` completions used to be swapped to the enclosing
    signature, so every parameter's info box showed the entire function
    docstring. Now we surface only the parameter's own description (empty when
    it can't be extracted, e.g. without `docstring_to_markdown`), never the
    function summary or a sibling parameter's text.
    """
    other_code = (
        "def my_func(alpha, beta):\n"
        '    """SUMMARY_MARKER.\n\n'
        "    Args:\n"
        "        alpha: ALPHA_MARKER.\n"
        "        beta: BETA_MARKER.\n"
        '    """\n'
        "    return alpha\n"
    )
    content = _run_complete("my_func(al", other_code=other_code)
    options = {o["name"]: o for o in content["options"]}
    assert "alpha=" in options
    info = options["alpha="]["completion_info"]
    assert "SUMMARY_MARKER" not in info
    assert "BETA_MARKER" not in info


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


class _FakeCompletion:
    """Stand-in for jedi.api.classes.Completion.

    Tracks whether `type` was accessed and how often `infer()` ran so we can
    assert we didn't pay the (expensive) jedi inference cost in the fast path.
    """

    def __init__(
        self,
        name: str,
        completion_type: str = "function",
        raise_on_type: bool = False,
        inferred: list[Any] | None = None,
    ) -> None:
        self.name = name
        self._type = completion_type
        self._raise_on_type = raise_on_type
        self._inferred = inferred or []
        self.type_access_count = 0
        self.docstring_called = False
        self.infer_count = 0

    @property
    def type(self) -> str:
        self.type_access_count += 1
        if self._raise_on_type:
            raise AssertionError(
                "completion.type accessed when it should have been skipped"
            )
        return self._type

    def docstring(self, *_args: Any, **_kwargs: Any) -> str:
        self.docstring_called = True
        return ""

    def get_signatures(self) -> list[Any]:
        return []

    def get_type_hint(self) -> str:
        return "int"

    def infer(self) -> list[Any]:
        self.infer_count += 1
        return self._inferred


def test_get_completion_option_skips_type_when_compute_type_false() -> None:
    completion = _FakeCompletion("foo", raise_on_type=True)

    option = _get_completion_option(
        completion,
        compute_completion_info=False,
        compute_type=False,
    )

    assert option.name == "foo"
    assert option.type == ""
    assert option.completion_info == ""
    assert completion.type_access_count == 0


def test_get_completion_option_computes_type_by_default() -> None:
    completion = _FakeCompletion("foo", completion_type="class")

    option = _get_completion_option(
        completion,
        compute_completion_info=False,
    )

    assert option.type == "class"
    assert completion.type_access_count == 1


def test_get_completion_option_skips_all_inference_when_type_skipped() -> None:
    """When `compute_type=False`, we also skip docstrings and signatures.
    The whole point of `compute_type=False` is "we're out of budget", so
    further jedi inference (docstring, signature) would defeat the purpose.
    """
    completion = _FakeCompletion("foo", raise_on_type=True)

    option = _get_completion_option(
        completion,
        compute_completion_info=True,
        compute_type=False,
    )

    assert option.name == "foo"
    assert option.type == ""
    assert option.completion_info == ""
    assert completion.type_access_count == 0
    assert not completion.docstring_called


def test_get_completion_options_skips_docstrings_past_limit() -> None:
    completions = [_FakeCompletion(f"attr_{i}") for i in range(10)]

    options = _get_completion_options(
        completions, prefix="", limit=5, timeout=5.0
    )

    assert len(options) == 10
    assert all(opt.completion_info == "" for opt in options)
    # Types are still computed since we're well under the timeout
    assert all(c.type_access_count == 1 for c in completions)


def test_get_completion_options_keeps_docstrings_under_limit() -> None:
    completions = [_FakeCompletion(f"attr_{i}") for i in range(3)]

    _get_completion_options(completions, prefix="", limit=10, timeout=5.0)

    # All three completions should have had docstring() invoked
    assert all(c.docstring_called for c in completions)


def test_get_completion_options_bails_out_when_timeout_elapsed() -> None:
    """Once the time budget is blown, subsequent completions skip both type
    inference and docstring lookup — this is the key knob that keeps cold
    completions from taking 10+ seconds on heavy libraries.
    """
    completions = [_FakeCompletion(f"attr_{i}") for i in range(4)]

    # Burn time on the first call so the rest see an expired budget.
    original_monotonic = time.monotonic
    times = iter([0.0, 0.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0])

    with mock.patch(
        "marimo._runtime.complete.time.monotonic",
        side_effect=lambda: next(times, original_monotonic()),
    ):
        options = _get_completion_options(
            completions, prefix="", limit=100, timeout=1.0
        )

    # First one completes normally, the rest should have no info or type
    assert options[0].completion_info != "" or completions[0].docstring_called
    assert options[0].type == "function"
    for opt in options[1:]:
        assert opt.type == ""
        assert opt.completion_info == ""


def test_get_completion_options_respects_prefix_filter() -> None:
    """Underscore names are filtered out by `_should_include_name`."""
    completions = [
        _FakeCompletion("public"),
        _FakeCompletion("_private"),
        _FakeCompletion("__dunder__"),
    ]

    options = _get_completion_options(
        completions, prefix="", limit=100, timeout=5.0
    )

    assert [opt.name for opt in options] == ["public"]


def _completion_for(code: str, name: str) -> Any:
    """Return the Jedi completion named `name` at the end of `code`."""
    script = jedi.Script(code=code)
    lines = code.split("\n")
    completions = script.complete(line=len(lines), column=len(lines[-1]))
    matches = [c for c in completions if c.name == name]
    assert matches, (
        f"no completion named {name!r}; got {[c.name for c in completions]}"
    )
    return matches[0]


def test_completion_info_resolves_aliased_function() -> None:
    """Aliases to a function show the underlying docstring + signature.

    Regression test for #9822: `alias = func` is reported by Jedi as a
    `statement`, which previously fell through to a bare type hint, dropping
    the docstring and signature highlighting in live docs / hover.
    """
    code = (
        "def my_documented_func(arg: int) -> None:\n"
        '    """Docstring for the aliased function."""\n'
        "    print(arg)\n"
        "\n"
        "alias = my_documented_func\n"
        "alias"
    )
    completion = _completion_for(code, "alias")
    assert completion.type == "statement"

    info = _get_completion_info(completion)
    assert "Docstring for the aliased function." in info
    # Signature is rendered as a highlighted python code block.
    assert "codehilite" in info
    assert "my_documented_func" in info


def test_completion_info_resolves_aliased_class() -> None:
    code = (
        "class MyDocumentedClass:\n"
        '    """Docstring for the aliased class."""\n'
        "\n"
        "Alias = MyDocumentedClass\n"
        "Alias"
    )
    completion = _completion_for(code, "Alias")
    assert completion.type == "statement"

    info = _get_completion_info(completion)
    assert "Docstring for the aliased class." in info


def test_completion_info_plain_value_statement_uses_type_hint() -> None:
    """Statements resolving to plain values keep the type-hint fallback rather
    than surfacing a builtin's docstring."""
    code = "answer = 42\nanswer"
    completion = _completion_for(code, "answer")
    assert completion.type == "statement"

    info = _get_completion_info(completion)
    assert info == "answer: int"
    assert "codehilite" not in info


def test_completion_info_ambiguous_alias_falls_back_to_type_hint() -> None:
    """When `infer()` resolves to multiple definitions (e.g. a conditional
    assignment), don't guess a docstring — defer to the type hint."""
    code = (
        "import random\n"
        "\n"
        "def foo(a: int) -> int:\n"
        '    """Foo docstring."""\n'
        "    return a\n"
        "\n"
        "def bar(b: str) -> str:\n"
        '    """Bar docstring."""\n'
        "    return b\n"
        "\n"
        "chosen = foo if random.random() > 0.5 else bar\n"
        "chosen"
    )
    completion = _completion_for(code, "chosen")
    assert completion.type == "statement"

    info = _get_completion_info(completion)
    assert info.startswith("chosen: ")
    assert "Foo docstring." not in info
    assert "Bar docstring." not in info
    assert "codehilite" not in info


def test_infer_skipped_for_statements_past_limit() -> None:
    """The docstring limit must prevent `.infer()` fan-out.

    Aliased-statement resolution calls `jedi`'s `infer()`, which "follows all
    results" and is very slow across large completion sets (e.g. `np.`). The
    `len(completions) <= limit` gate has to keep us out of that path entirely.
    """
    completions = [
        _FakeCompletion(f"v{i}", completion_type="statement")
        for i in range(10)
    ]

    _get_completion_options(completions, prefix="", limit=5, timeout=5.0)

    assert all(c.infer_count == 0 for c in completions)


def test_infer_only_runs_for_statements_under_budget() -> None:
    """Within budget, only statement completions infer (once each); other
    types go straight to `_get_docstring` and never touch `infer()`."""
    statements = [
        _FakeCompletion(f"s{i}", completion_type="statement") for i in range(3)
    ]
    functions = [
        _FakeCompletion(f"f{i}", completion_type="function") for i in range(3)
    ]

    _get_completion_options(
        statements + functions,
        prefix="",
        limit=100,
        timeout=5.0,
    )

    assert all(c.infer_count == 1 for c in statements)
    assert all(c.infer_count == 0 for c in functions)


def test_infer_skipped_once_timeout_elapsed() -> None:
    """Once the time budget is blown, remaining statements skip `.infer()`
    just like they skip type/docstring inference."""
    completions = [
        _FakeCompletion(f"v{i}", completion_type="statement") for i in range(4)
    ]

    original_monotonic = time.monotonic
    times = iter([0.0, 0.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0])

    with mock.patch(
        "marimo._runtime.complete.time.monotonic",
        side_effect=lambda: next(times, original_monotonic()),
    ):
        _get_completion_options(completions, prefix="", limit=100, timeout=1.0)

    # First completion is under budget and infers; the rest are skipped.
    assert completions[0].infer_count == 1
    assert all(c.infer_count == 0 for c in completions[1:])


def test_falls_back_to_interpreter_when_static_analysis_raises() -> None:
    """A jedi static-analysis crash should not kill completion.

    jedi's static analysis can raise while inferring some code (e.g.
    resolving the generic return type of `polars.concat` crashes with
    an AttributeError, https://github.com/davidhalter/jedi/issues/1990).
    The interpreter-based fallback should still get a chance to run.

    https://github.com/marimo-team/marimo/issues/10055
    """

    class MyData:
        def with_columns(self) -> None: ...

        def with_row_index(self) -> None: ...

    glbls = {"my_obj": MyData()}

    with mock.patch(
        "marimo._runtime.complete._get_completions_with_script",
        side_effect=AttributeError(
            "'TreeInstance' object has no attribute 'with_generics'"
        ),
    ):
        _script, completions = _get_completions(
            ["my_obj = MyData()"], "my_obj.wi", glbls, threading.RLock()
        )

    names = [completion.name for completion in completions]
    assert "with_columns" in names
    assert "with_row_index" in names


@pytest.mark.skipif(not HAS_POLARS, reason="polars not installed")
def test_polars_concat_attribute_completion() -> None:
    """Attribute completion works for variables assigned from `pl.concat`.

    Regression test for https://github.com/marimo-team/marimo/issues/10055:
    jedi's static analysis crashes on `pl.concat(...)` (jedi#1990), which
    used to skip the interpreter fallback and return no completions.
    """
    code = (
        "import polars as pl\n"
        'df_a = pl.DataFrame({"a": [1]})\n'
        'df_b = pl.DataFrame({"a": [2]})\n'
        "df_x = pl.concat([df_a, df_b])"
    )
    glbls: dict[str, Any] = {}
    exec(code, glbls)

    _script, completions = _get_completions(
        [code], "df_x.wi", glbls, threading.RLock()
    )

    names = [completion.name for completion in completions]
    assert "with_columns" in names
