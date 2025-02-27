from __future__ import annotations

import sys
from typing import Any, cast

from marimo._dependencies.dependencies import DependencyManager
from marimo._output.formatters.structures import (
    StructuresFormatter,
    format_structure,
)
from marimo._output.formatting import get_formatter
from marimo._output.md import md
from marimo._plugins.ui._impl.input import slider
from marimo._runtime.runtime import Kernel
from tests.conftest import ExecReqProvider


def get_and_format(obj: Any) -> Any:
    formatter = get_formatter(obj)
    assert formatter is not None
    return formatter(obj)


async def test_matplotlib_special_case(
    executing_kernel: Kernel, exec_req: ExecReqProvider
) -> None:
    if DependencyManager.matplotlib.has() and DependencyManager.numpy.has():
        from marimo._output.formatters.formatters import register_formatters

        register_formatters()

        await executing_kernel.run(
            [
                exec_req.get(
                    """
                    import numpy as np
                    import matplotlib.pyplot as plt
                    from marimo._output.formatting import get_formatter

                    arr = np.random.randn(12, 5)
                    lines = plt.plot(arr)
                    formatter = get_formatter(lines)
                    """
                )
            ]
        )

        formatter = executing_kernel.globals["formatter"]
        lines = executing_kernel.globals["lines"]
        assert formatter is not None
        assert formatter(lines)[0].startswith("image")


def test_format_structure_types() -> None:
    formatted = cast(
        list[Any], format_structure(["hello", True, False, None, 1, 1.0])
    )
    assert formatted[0] == "hello"
    assert formatted[1] is True
    assert formatted[2] is False
    assert formatted[3] is None
    assert formatted[4] == 1
    assert formatted[5] == "text/plain+float:1.0"


def test_format_structure_simple() -> None:
    StructuresFormatter().register()

    assert get_and_format([1, 2, 3, True, False, 1.0, 2.5]) == (
        "application/json",
        '[1, 2, 3, true, false, "text/plain+float:1.0", "text/plain+float:2.5"]',
    )
    assert get_and_format((1, 2, 3, True, False, 1.0, 2.5)) == (
        "application/json",
        '[1, 2, 3, true, false, "text/plain+float:1.0", "text/plain+float:2.5"]',
    )
    assert get_and_format(
        {"a": 1, "b": 2, "c": 3, "d": True, "e": False, "f": 1.0, "g": 2.5}
    ) == (
        "application/json",
        '{"a": 1, "b": 2, "c": 3, "d": true, "e": false, "f": "text/plain+float:1.0", "g": "text/plain+float:2.5"}',
    )


def test_format_structure_nested() -> None:
    StructuresFormatter().register()

    nested_structure = {
        "a": [1, 2, {"b": 3, "c": True}],
        "d": (4, 5, False, 1.0),
    }
    assert get_and_format(nested_structure) == (
        "application/json",
        '{"a": [1, 2, {"b": 3, "c": true}], "d": [4, 5, false, "text/plain+float:1.0"]}',
    )


def test_format_structure_nested_with_html() -> None:
    StructuresFormatter().register()

    _markdown = md("# hello")
    _slider = slider(start=0, stop=100)
    nested_structure = [1, _markdown, _slider]

    def escape(s: str) -> str:
        return s.replace('"', '\\"')

    assert get_and_format(nested_structure) == (
        "application/json",
        f'[1, "text/html:{escape(_markdown.text)}", "text/html:{escape(_slider.text)}"]',
    )


def test_format_structure_cyclic() -> None:
    StructuresFormatter().register()

    cyclic_structure = []
    cyclic_structure.append(cyclic_structure)

    assert get_and_format(cyclic_structure) == (
        "text/plain",
        "[[...]]",
    )


def test_format_structure_subclasses_no_repr() -> None:
    StructuresFormatter().register()

    class CustomList(list):
        pass

    custom_list = CustomList([1, 2, 3])
    assert get_and_format(custom_list) == ("application/json", "[1, 2, 3]")

    class CustomDict(dict):
        pass

    custom_dict = CustomDict({"a": 1, "b": 2, "c": 3})
    assert get_and_format(custom_dict) == (
        "application/json",
        '{"a": 1, "b": 2, "c": 3}',
    )

    class CustomTuple(tuple):
        pass

    custom_tuple = CustomTuple((1, 2, 3))
    assert get_and_format(custom_tuple) == ("application/json", "[1, 2, 3]")


def test_format_structure_subclasses_with_repr_html() -> None:
    StructuresFormatter().register()

    class CustomList(list):
        def _repr_html_(self) -> str:
            return "<b>CustomList</b>"

    custom_list = CustomList([1, 2, 3])
    assert get_and_format(custom_list) == ("text/html", "<b>CustomList</b>")

    class CustomDict(dict):
        def _repr_html_(self) -> str:
            return "<b>CustomDict</b>"

    custom_dict = CustomDict({"a": 1, "b": 2, "c": 3})
    assert get_and_format(custom_dict) == ("text/html", "<b>CustomDict</b>")

    class CustomTuple(tuple):
        def _repr_html_(self) -> str:
            return "<b>CustomTuple</b>"

    custom_tuple = CustomTuple((1, 2, 3))
    assert get_and_format(custom_tuple) == ("text/html", "<b>CustomTuple</b>")


def test_format_structure_subclasses_with_different_built_in_repr() -> None:
    StructuresFormatter().register()

    class CustomList(list):
        def __init__(self) -> None:
            super().__init__((1, 2, 3))

        def __repr__(self) -> str:
            return "CustomList(a=1, b=2, c=3)"

    custom_list = CustomList()
    assert get_and_format(custom_list) == (
        "text/html",
        "<pre style='font-size: 12px'>CustomList(a=1, b=2, c=3)</pre>",
    )

    class CustomDict(dict):
        def __init__(self) -> None:
            super().__init__({"a": 1, "b": 2, "c": 3})

        def __repr__(self) -> str:
            return "CustomDict(a=1, b=2, c=3)"

    custom_dict = CustomDict()
    assert get_and_format(custom_dict) == (
        "text/html",
        "<pre style='font-size: 12px'>CustomDict(a=1, b=2, c=3)</pre>",
    )

    class CustomTuple(tuple):
        def __init__(self) -> None:
            super().__init__()

        def __repr__(self) -> str:
            return "CustomTuple(a=1, b=2, c=3)"

    custom_tuple = CustomTuple()
    assert get_and_format(custom_tuple) == (
        "text/html",
        "<pre style='font-size: 12px'>CustomTuple(a=1, b=2, c=3)</pre>",
    )

    assert get_and_format(sys.version_info)[1].startswith(
        "<pre style='font-size: 12px'>sys.version_info(major=3"
    )


def test_format_structure_set() -> None:
    test_set = {1, 2, 3}
    assert format_structure([test_set]) == (["text/plain+set:{1, 2, 3}"])


def test_format_structure_tuple() -> None:
    test_tuple = (1, 2, 3)
    assert format_structure(test_tuple) == (1, 2, 3)
