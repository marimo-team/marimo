from __future__ import annotations

import json
import sys
from collections import defaultdict
from typing import Any, cast

from inline_snapshot import snapshot

from marimo._dependencies.dependencies import DependencyManager
from marimo._output.formatters.structures import (
    StructuresFormatter,
    format_structure,
    is_structures_formatter,
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
        mimetype = formatter(lines)[0]
        assert (
            mimetype.startswith("image")
            or mimetype == "application/vnd.marimo+mimebundle"
        )


async def test_matplotlib_boxplot_dict_special_case(
    executing_kernel: Kernel, exec_req: ExecReqProvider
) -> None:
    """Test that boxplot dict (containing artist lists) formats as single figure."""
    if DependencyManager.matplotlib.has():
        from marimo._output.formatters.formatters import register_formatters

        register_formatters()

        await executing_kernel.run(
            [
                exec_req.get(
                    """
                    import matplotlib.pyplot as plt
                    from marimo._output.formatting import get_formatter

                    fig, ax = plt.subplots()
                    boxplot_result = ax.boxplot([0])
                    formatter = get_formatter(boxplot_result)
                    """
                )
            ]
        )

        formatter = executing_kernel.globals["formatter"]
        boxplot_result = executing_kernel.globals["boxplot_result"]
        assert formatter is not None
        mimetype, _data = formatter(boxplot_result)
        # Should be a single image, not JSON with multiple formatted artists
        assert (
            mimetype.startswith("image")
            or mimetype == "application/vnd.marimo+mimebundle"
        ), f"Expected image mimetype, got {mimetype}"


async def test_matplotlib_violinplot_dict_special_case(
    executing_kernel: Kernel, exec_req: ExecReqProvider
) -> None:
    """Test that violinplot dict (with artist values) formats as single figure."""
    if DependencyManager.matplotlib.has():
        from marimo._output.formatters.formatters import register_formatters

        register_formatters()

        await executing_kernel.run(
            [
                exec_req.get(
                    """
                    import matplotlib.pyplot as plt
                    from marimo._output.formatting import get_formatter

                    fig, ax = plt.subplots()
                    violinplot_result = ax.violinplot([1, 2, 3])
                    formatter = get_formatter(violinplot_result)
                    """
                )
            ]
        )

        formatter = executing_kernel.globals["formatter"]
        violinplot_result = executing_kernel.globals["violinplot_result"]
        assert formatter is not None
        mimetype, _data = formatter(violinplot_result)
        # Should be a single image, not JSON with multiple formatted artists
        assert (
            mimetype.startswith("image")
            or mimetype == "application/vnd.marimo+mimebundle"
        ), f"Expected image mimetype, got {mimetype}"


async def test_matplotlib_mixed_artists_and_non_artists(
    executing_kernel: Kernel, exec_req: ExecReqProvider
) -> None:
    """Test that structures with mixed artists and non-artists fall through to JSON."""
    if DependencyManager.matplotlib.has():
        from marimo._output.formatters.formatters import register_formatters

        register_formatters()

        await executing_kernel.run(
            [
                exec_req.get(
                    """
                    import matplotlib.pyplot as plt
                    from marimo._output.formatting import get_formatter

                    fig, ax = plt.subplots()
                    line = ax.plot([1, 2, 3])[0]
                    # Mixed list: one Artist and one non-Artist
                    mixed_list = [line, "not an artist"]
                    formatter_list = get_formatter(mixed_list)
                    # Mixed dict: Artist list and non-Artist list
                    mixed_dict = {"line": [line], "other": [1, 2, 3]}
                    formatter_dict = get_formatter(mixed_dict)
                    # Dict with non-list/tuple/Artist value (e.g., a string)
                    dict_with_scalar = {"line": [line], "label": "my label"}
                    formatter_scalar = get_formatter(dict_with_scalar)
                    plt.close(fig)
                    """
                )
            ]
        )

        # Test mixed list falls through to JSON formatting
        formatter_list = executing_kernel.globals["formatter_list"]
        mixed_list = executing_kernel.globals["mixed_list"]
        assert formatter_list is not None
        mimetype, _ = formatter_list(mixed_list)
        assert mimetype == "application/json", (
            f"Mixed list should fall through to JSON, got {mimetype}"
        )

        # Test mixed dict falls through to JSON formatting
        formatter_dict = executing_kernel.globals["formatter_dict"]
        mixed_dict = executing_kernel.globals["mixed_dict"]
        assert formatter_dict is not None
        mimetype, _ = formatter_dict(mixed_dict)
        assert mimetype == "application/json", (
            f"Mixed dict should fall through to JSON, got {mimetype}"
        )

        # Test dict with scalar value falls through to JSON formatting
        formatter_scalar = executing_kernel.globals["formatter_scalar"]
        dict_with_scalar = executing_kernel.globals["dict_with_scalar"]
        assert formatter_scalar is not None
        mimetype, _ = formatter_scalar(dict_with_scalar)
        assert mimetype == "application/json", (
            f"Dict with scalar value should fall through to JSON, got {mimetype}"
        )


async def test_matplotlib_dict_with_axes_and_string(
    executing_kernel: Kernel, exec_req: ExecReqProvider
) -> None:
    """Test that a dict mixing Axes (Artist) and string falls through to JSON.

    Regression test for the case shown in issue #6838 where:
        plt.plot([1, 2])
        l = {"key1": plt.gca(), "key2": "Hello, World!"}
        l
    Should NOT render as a matplotlib figure - should be JSON.
    """
    if DependencyManager.matplotlib.has():
        from marimo._output.formatters.formatters import register_formatters

        register_formatters()

        await executing_kernel.run(
            [
                exec_req.get(
                    """
                    import matplotlib.pyplot as plt
                    from marimo._output.formatting import get_formatter

                    plt.plot([1, 2])
                    result = {"key1": plt.gca(), "key2": "Hello, World!"}
                    formatter = get_formatter(result)
                    plt.close('all')
                    """
                )
            ]
        )

        formatter = executing_kernel.globals["formatter"]
        result = executing_kernel.globals["result"]
        assert formatter is not None
        mimetype, _ = formatter(result)
        assert mimetype == "application/json", (
            f"Dict with Axes and string should fall through to JSON, got {mimetype}"
        )


async def test_matplotlib_hist_special_case(
    executing_kernel: Kernel, exec_req: ExecReqProvider
) -> None:
    """Test that hist() tuple output formats as single figure.

    ax.hist() returns a tuple of (n, bins, patches) where patches is a
    BarContainer (which is a tuple subclass of Rectangle artists).
    The tuple itself contains non-Artist elements (n, bins arrays),
    so it should fall through to JSON formatting.
    """
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

                    fig, ax = plt.subplots()
                    hist_result = ax.hist([1, 2, 2, 3, 3, 3])
                    formatter = get_formatter(hist_result)
                    plt.close(fig)
                    """
                )
            ]
        )

        formatter = executing_kernel.globals["formatter"]
        hist_result = executing_kernel.globals["hist_result"]
        assert formatter is not None
        mimetype, _ = formatter(hist_result)
        # hist() returns (n, bins, patches) - n and bins are arrays,
        # so this should fall through to JSON
        assert mimetype == "application/json", (
            f"hist() tuple should fall through to JSON, got {mimetype}"
        )


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

    bigint = 2**64

    nested_structure = {
        "a": [1, 2, {"b": 3, "c": True}],
        "d": (4, 5, False, 1.0, bigint),
    }
    assert get_and_format(nested_structure) == (
        "application/json",
        f'{{"a": [1, 2, {{"b": 3, "c": true}}], "d": [4, 5, false, "text/plain+float:1.0", "text/plain+bigint:{bigint}"]}}',
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
        f'[1, "text/markdown:{escape(_markdown.text)}", "text/html:{escape(_slider.text)}"]',
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
        "<pre class='text-xs'>CustomList(a=1, b=2, c=3)</pre>",
    )

    class CustomDict(dict):
        def __init__(self) -> None:
            super().__init__({"a": 1, "b": 2, "c": 3})

        def __repr__(self) -> str:
            return "CustomDict(a=1, b=2, c=3)"

    custom_dict = CustomDict()
    assert get_and_format(custom_dict) == (
        "text/html",
        "<pre class='text-xs'>CustomDict(a=1, b=2, c=3)</pre>",
    )

    class CustomTuple(tuple):
        def __init__(self) -> None:
            super().__init__()

        def __repr__(self) -> str:
            return "CustomTuple(a=1, b=2, c=3)"

    custom_tuple = CustomTuple()
    assert get_and_format(custom_tuple) == (
        "text/html",
        "<pre class='text-xs'>CustomTuple(a=1, b=2, c=3)</pre>",
    )

    assert get_and_format(sys.version_info)[1].startswith(
        "<pre class='text-xs'>sys.version_info(major=3"
    )


def test_format_structure_set() -> None:
    # Set values now use a JSON-list payload (matching tuple/frozenset
    # and the key-side encoding) so the frontend renders them with the
    # same double-quoted element form as the rest of the tree.
    test_set = {1, 2, 3}
    formatted = format_structure([test_set])
    assert isinstance(formatted, list)
    (leaf,) = formatted
    assert leaf.startswith("text/plain+set:")
    payload = json.loads(leaf[len("text/plain+set:") :])
    assert sorted(payload) == [1, 2, 3]


def test_format_structure_frozenset() -> None:
    """Frozenset values use the dedicated text/plain+frozenset: mimetype."""
    formatted = format_structure([frozenset({1, 2, 3})])
    assert isinstance(formatted, list)
    (leaf,) = formatted
    assert leaf.startswith("text/plain+frozenset:")
    payload = json.loads(leaf[len("text/plain+frozenset:") :])
    assert sorted(payload) == [1, 2, 3]


def test_format_structure_empty_set_and_frozenset() -> None:
    """Empty set/frozenset values encode as empty JSON lists."""
    assert format_structure([set()]) == snapshot(["text/plain+set:[]"])
    assert format_structure([frozenset()]) == snapshot(
        ["text/plain+frozenset:[]"]
    )


def test_format_structure_dict_non_string_keys_do_not_collide() -> None:
    """Regression test for https://github.com/marimo-team/marimo/issues/9288.

    JSON object keys are always strings, so a Python dict that mixes
    equal-looking string and non-string keys (e.g. {"2": ..., 2: ...})
    must not silently collapse to a single entry once the JSON is parsed
    in the browser.
    """
    StructuresFormatter().register()

    my_map = {"2": "oh", 2: "no"}
    mimetype, data = get_and_format(my_map)
    assert mimetype == "application/json"

    # The serialized form must round-trip through JSON.parse without losing
    # entries (in the browser, `JSON.parse` keeps only the last duplicate key).
    parsed = json.loads(data)
    assert len(parsed) == len(my_map)
    assert parsed == snapshot({"2": "oh", "text/plain+int:2": "no"})


def test_format_structure_dict_primitive_keys_encoded() -> None:
    """Non-string primitive keys are mimetype-encoded on the wire."""
    StructuresFormatter().register()

    _, data = get_and_format(
        {
            "plain": 1,
            2: "int",
            2.5: "float",
            True: "bool_true",
            False: "bool_false",
            None: "none",
        }
    )
    assert json.loads(data) == snapshot(
        {
            "plain": 1,
            "text/plain+int:2": "int",
            "text/plain+float:2.5": "float",
            "text/plain+bool:True": "bool_true",
            "text/plain+bool:False": "bool_false",
            "text/plain+none:": "none",
        }
    )


def test_format_structure_dict_bigint_key_encoded_as_int() -> None:
    """Keys use text/plain+int: regardless of size (no JS precision concern)."""
    StructuresFormatter().register()

    _, data = get_and_format({2**64: "v"})
    assert json.loads(data) == snapshot(
        {"text/plain+int:18446744073709551616": "v"}
    )


def test_format_structure_dict_nan_inf_float_keys_are_strict_json() -> None:
    """NaN/Inf keys must not emit bare `NaN`/`Infinity` (invalid JSON)."""
    StructuresFormatter().register()

    _, data = get_and_format(
        {float("nan"): "n", float("inf"): "p", -float("inf"): "m"}
    )
    # json.loads is strict and would fail if we emitted `NaN`/`Infinity`.
    assert json.loads(data) == snapshot(
        {
            "text/plain+float:nan": "n",
            "text/plain+float:inf": "p",
            "text/plain+float:-inf": "m",
        }
    )


def test_format_structure_dict_tuple_key_encoded() -> None:
    """Regression test for #2667 — tuple keys keep their type on the wire."""
    StructuresFormatter().register()

    _, data = get_and_format({(1, 2, 3): 4})
    assert json.loads(data) == snapshot({"text/plain+tuple:[1, 2, 3]": 4})


def test_format_structure_dict_frozenset_key_encoded() -> None:
    """Frozenset keys use a dedicated mimetype, distinct from set values."""
    StructuresFormatter().register()

    _, data = get_and_format({frozenset({1, 2}): "v"})
    parsed = json.loads(data)
    (key,) = parsed
    assert key.startswith("text/plain+frozenset:")
    # Sort to dodge the non-deterministic frozenset iteration order.
    payload = sorted(json.loads(key[len("text/plain+frozenset:") :]))
    assert payload == snapshot([1, 2])


def test_format_structure_dict_empty_frozenset_key_encoded() -> None:
    """Empty frozenset key encodes as `text/plain+frozenset:[]`."""
    StructuresFormatter().register()

    _, data = get_and_format({frozenset(): "v"})
    assert json.loads(data) == snapshot({"text/plain+frozenset:[]": "v"})


def test_format_structure_dict_single_element_tuple_key_encoded() -> None:
    """1-element tuple key encodes as a JSON list of length 1."""
    StructuresFormatter().register()

    _, data = get_and_format({(42,): "v"})
    assert json.loads(data) == snapshot({"text/plain+tuple:[42]": "v"})


def test_format_structure_dict_fallback_string_is_escaped() -> None:
    """A custom key whose `str()` starts with `text/plain+` must be escaped.

    Without the escape the frontend would decode it as a typed key and
    render it incorrectly. This covers the `str(k)` fallback for unusual
    hashables.
    """

    class Hostile:
        def __str__(self) -> str:
            return "text/plain+int:99"

        def __hash__(self) -> int:
            return 0

        def __eq__(self, other: object) -> bool:
            return isinstance(other, Hostile)

    StructuresFormatter().register()

    _, data = get_and_format({Hostile(): "v"})
    assert json.loads(data) == snapshot(
        {"text/plain+str:text/plain+int:99": "v"}
    )


def test_format_structure_dict_string_key_that_looks_encoded_is_escaped() -> (
    None
):
    """Literal string keys starting with `text/plain+` are escaped."""
    StructuresFormatter().register()

    _, data = get_and_format({"text/plain+int:2": "hello"})
    assert json.loads(data) == snapshot(
        {"text/plain+str:text/plain+int:2": "hello"}
    )


def test_format_structure_dict_nested_keys_encoded() -> None:
    """Encoding applies at every nesting level."""
    StructuresFormatter().register()

    _, data = get_and_format({"outer": {1: "inner", (2, 3): "tup"}})
    assert json.loads(data) == snapshot(
        {
            "outer": {
                "text/plain+int:1": "inner",
                "text/plain+tuple:[2, 3]": "tup",
            }
        }
    )


def test_format_structure_dict_python_level_bool_int_collapse_preserved() -> (
    None
):
    """Python collapses True/1 before we see the dict — encoder preserves that."""
    StructuresFormatter().register()

    # True/1/1.0 are hash-equal in Python, so assigning them in sequence
    # yields a single-entry dict: first-inserted key wins, later assignments
    # only update the value. Built up programmatically to dodge ruff's
    # duplicate-literal-key warning.
    d: dict[object, object] = {}
    d[True] = False
    d[1] = "bar"
    d[1.0] = "baz"
    assert len(d) == 1

    _, data = get_and_format(d)
    # That one entry encodes under the bool prefix (first-inserted key wins).
    assert json.loads(data) == snapshot({"text/plain+bool:True": "baz"})


def test_format_structure_dict_plain_string_keys_unchanged() -> None:
    """Common case — plain string-key dicts serialize exactly as before."""
    StructuresFormatter().register()

    assert get_and_format({"a": 1, "b": 2}) == snapshot(
        ("application/json", '{"a": 1, "b": 2}')
    )


def _reject_non_finite(literal: str) -> float:
    # `parse_constant` fires for bare `NaN`, `Infinity`, and `-Infinity`.
    # Python's `json.loads` accepts these by default (non-spec) — passing a
    # raising hook makes the test match the JS `JSON.parse` behavior we
    # actually care about.
    raise AssertionError(f"outer JSON contained bare {literal!r}")


def test_format_structure_tuple_key_with_nan_outer_json_is_strict() -> None:
    """Tuple keys with non-finite floats are embedded strings — the outer
    JSON must be strict per the JS `JSON.parse` spec (no bare `NaN` /
    `Infinity` at the top level).

    Those tokens live inside the embedded tuple payload *string*, not at
    the outer JSON level, so the frontend's outer `JSON.parse` succeeds
    and it then calls `jsonParseWithSpecialChar` on the embedded
    payload. Previously the bare token appeared at the top level and
    broke the outer parse.
    """
    StructuresFormatter().register()

    _, data = get_and_format(
        {(float("nan"),): "n", (float("inf"), -float("inf")): "i"}
    )
    # `parse_constant` raises on bare NaN/Infinity at the JSON layer —
    # matching JS `JSON.parse` strictness. `json.loads` alone accepts
    # them by default, which is too lenient to test the contract.
    parsed = json.loads(data, parse_constant=_reject_non_finite)
    assert parsed == {
        "text/plain+tuple:[NaN]": "n",
        "text/plain+tuple:[Infinity, -Infinity]": "i",
    }


def test_format_structure_frozenset_value_with_nan_outer_json_is_strict() -> (
    None
):
    """Frozenset values with non-finite floats parse strictly at the outer level."""
    StructuresFormatter().register()

    _, data = get_and_format({"k": frozenset({float("inf"), 1})})
    # Outer parse is strict (JS-`JSON.parse`-compatible).
    parsed = json.loads(data, parse_constant=_reject_non_finite)
    key = parsed["k"]
    assert key.startswith("text/plain+frozenset:")
    # The embedded payload contains bare `Infinity`; the frontend parses
    # it with `jsonParseWithSpecialChar`. Python's permissive `json.loads`
    # is fine here because we're just inspecting the embedded content.
    payload = json.loads(key[len("text/plain+frozenset:") :])
    assert set(payload) == {1, float("inf")}


def test_format_structure_frozenset_key_with_nan_outer_json_is_strict() -> (
    None
):
    """Frozenset keys with non-finite floats parse strictly at the outer level."""
    StructuresFormatter().register()

    _, data = get_and_format({frozenset({float("nan")}): "v"})
    # Outer parse is strict — the bare `NaN` lives inside the key string.
    parsed = json.loads(data, parse_constant=_reject_non_finite)
    (key,) = parsed
    assert key == "text/plain+frozenset:[NaN]"


def test_format_structure_tuple_value_with_nan_is_strict_json() -> None:
    """Tuple values with non-finite floats round-trip via scalar sentinels.

    Tuple values don't hit the tuple-encoder path because `flatten`
    recurses into tuples before leaf formatting — each float is handled
    by `_leaf_formatter` and emitted as its own `text/plain+float:`
    sentinel string.
    """
    StructuresFormatter().register()

    formatted = format_structure([(float("nan"), float("inf"))])
    assert formatted == [("text/plain+float:nan", "text/plain+float:inf")]


def test_format_structure_bigint() -> None:
    bigint = 2**64
    assert format_structure([bigint]) == ([f"text/plain+bigint:{bigint}"])


def test_format_structure_tuple() -> None:
    test_tuple = (1, 2, 3)
    assert format_structure(test_tuple) == (1, 2, 3)


def test_format_structure_defaultdict() -> None:
    StructuresFormatter().register()

    # Test with default factory as int
    d = defaultdict(int)
    d["a"] = 1
    d["b"] = 2
    # Access a key that doesn't exist yet - should use default factory
    _ = d["c"]

    assert get_and_format(d) == (
        "application/json",
        '{"a": 1, "b": 2, "c": 0}',
    )

    # Test with default factory as list
    d = defaultdict(list)
    d["a"].append(1)
    d["b"].append(2)
    # Access a key that doesn't exist yet - should use default factory
    _ = d["c"]

    assert get_and_format(d) == (
        "application/json",
        '{"a": [1], "b": [2], "c": []}',
    )


def test_function_like_objects_are_pretty_inspected() -> None:
    from marimo._output.formatters.structures import StructuresFormatter

    StructuresFormatter().register()

    # Regular function
    def foo(x: int, y: str = "a") -> str:  # noqa: ARG001
        return "ok"

    fmt = get_formatter(foo)
    assert fmt is not None
    mime, data = fmt(foo)
    assert mime == "text/html"
    assert "function" in data or "def foo(" in data

    # Lambda
    lam = lambda z: z  # noqa: E731
    fmt = get_formatter(lam)
    assert fmt is not None
    mime, data = fmt(lam)
    assert mime == "text/html"
    assert "function" in data or "lambda" in data or "def" in data

    # Builtin function
    fmt = get_formatter(len)
    assert fmt is not None
    mime, data = fmt(len)
    assert mime == "text/html"
    # Builtins are labeled as instances of builtin_function_or_method
    assert "builtin_function_or_method" in data or "instance" in data

    # Method
    class C:
        def m(self, a: int) -> int:
            return a

    fmt = get_formatter(C.m)
    assert fmt is not None
    mime, data = fmt(C.m)
    assert mime == "text/html"
    assert "def m(" in data or "method" in data


def test_function_like_objects_use_repr_formatter_if_present() -> None:
    # Register a temporary repr formatter on a simple callable class
    class D:
        def __call__(self) -> None:  # pragma: no cover - just shape
            return None

        def _repr_html_(self) -> str:
            return "<b>HELLO</b>"

    # Ensure base structure formatter is registered
    from marimo._output.formatters.structures import StructuresFormatter

    StructuresFormatter().register()

    # The repr formatter should be honored and returned directly
    obj = D()
    fmt = get_formatter(obj)
    assert fmt is not None
    mime, data = fmt(obj)
    assert mime == "text/html"
    assert data == "<b>HELLO</b>"


def test_function_like_objects_fallback_on_exception() -> None:
    # Build a callable that raises when inspected/signatured to force fallback
    class Boom:
        def __call__(self, *args: object, **kwargs: object) -> None:  # noqa: ARG002
            return None

    b = Boom().__call__

    from marimo._output.formatters.structures import StructuresFormatter

    StructuresFormatter().register()
    fmt = get_formatter(b)
    assert fmt is not None
    mime, data = fmt(b)
    assert mime == "text/html" or mime == "text/plain"
    # Fallback path returns plain text repr wrapped via plain_text
    # which ultimately produces HTML; accept either to be robust.
    assert isinstance(data, str)
    assert len(data) > 0


def test_is_structures_formatter() -> None:
    assert is_structures_formatter(get_formatter(()))
    assert is_structures_formatter(get_formatter([]))
    assert is_structures_formatter(get_formatter({1: 2}))

    assert not is_structures_formatter(None)
    assert not is_structures_formatter(get_formatter(set()))
