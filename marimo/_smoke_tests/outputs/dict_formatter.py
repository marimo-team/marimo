import marimo

__generated_with = "0.23.2"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # `dict` formatter smoke test

    Manual visual check for the rich display of Python `dict`s. Run the
    notebook end-to-end and scroll through — every cell is a live dict
    output that exercises a different edge of the formatter.

    Things to eyeball across sections:

    - each entry survives the JSON round-trip (no silent drops)
    - string keys render quoted, non-string keys render with Python-style
      affordances (unquoted numerics / `True` / `False` / `None`, parens
      for tuples, `frozenset({...})` for frozensets)
    - the **copy** button next to each rendered dict yields valid Python
    - value formatting reuses the existing leaf machinery (floats, bigints,
      sets, tuples, html/markdown/images, …)

    Relevant issues: #9288, #2667.
    """)
    return


@app.cell
def _():
    import json

    import marimo as mo
    from collections import OrderedDict, defaultdict
    from marimo._output.formatters.structures import StructuresFormatter
    from marimo._output.formatting import get_formatter

    StructuresFormatter().register()

    def serialized(d):
        """Show the wire form + whether it survives JSON.parse on the frontend."""
        mime, data = get_formatter(d)(d)
        parsed = json.loads(data)
        return mo.md(f"""
    | | |
    |---|---|
    | mimetype | `{mime}` |
    | wire JSON | `{data}` |
    | entries after `JSON.parse` | {len(parsed)} |
    | Python `len()` | {len(d)} |
    """)

    return OrderedDict, defaultdict, mo, serialized


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 1 — baselines

    Common string-keyed dicts — the dominant case. Keys are quoted, values
    render with their native types. Empty dict, single-entry dict, and a
    record-shaped dict.
    """)
    return


@app.cell
def _():
    empty = {}
    empty
    return


@app.cell
def _():
    single = {"only": 1}
    single
    return


@app.cell
def _():
    record = {
        "name": "ada",
        "age": 36,
        "languages": ["analytical engine", "english"],
        "active": True,
        "spouse": None,
    }
    record
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 2 — value variety

    Dict values run through `_leaf_formatter`. Every primitive and common
    container type should render with the right affordance — floats as
    decimals, bigints at full precision, sets with `{}`, tuples with `()`,
    `None` as `None`, bools as `True`/`False`.
    """)
    return


@app.cell
def _():
    values = {
        "int": 42,
        "bigint": 2**70,
        "float": 3.14,
        "float_nan": float("nan"),
        "float_inf": float("inf"),
        "bool_t": True,
        "bool_f": False,
        "none": None,
        "str": "hello",
        "empty_str": "",
        "list": [1, 2, 3],
        "tuple": (1, 2, 3),
        "set": {1, 2, 3},
        "frozenset": frozenset({1, 2}),
        "dict": {"nested": True},
        "bytes": b"raw bytes",
    }
    values
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 3 — non-string keys

    Python dicts accept any hashable as a key; JSON objects don't. Non-string
    keys are encoded on the wire with `text/plain+<type>:` prefixes and
    decoded back to their original types in the viewer. Three things to check:
    each entry survives, keys render unquoted in the appropriate Python form,
    and collision-prone cases (`"2"` vs `2`, `"true"` vs `True`) stay distinct.
    """)
    return


@app.cell
def _():
    collision = {
        "2": "string two",
        2: "int two",
        "true": "string true",
        True: "bool True",
    }
    collision
    return (collision,)


@app.cell(hide_code=True)
def _(collision, serialized):
    serialized(collision)
    return


@app.cell
def _():
    primitives = {
        "plain_string": "string",
        2: "int",
        2**64: "bigint (still encoded as int — no precision concern)",
        2.5: "float",
        True: "bool True",
        False: "bool False",
        None: "None key",
    }
    primitives
    return


@app.cell
def _():
    nan_inf = {
        float("nan"): "not a number",
        float("inf"): "plus infinity",
        -float("inf"): "minus infinity",
        "normal": 1.5,
    }
    nan_inf
    return


@app.cell
def _():
    composites = {
        (1, 2, 3): "triple-tuple key",
        (0,): "single-element tuple",
        (): "empty tuple",
        frozenset({1, 2}): "frozenset key",
        frozenset(): "empty frozenset",
    }
    composites
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### Composite-key edge cases to eyeball

    Easy to regress, so listed on their own:

    - **1-element tuple** renders as `(0,)`, *not* `(0)` — the trailing comma
      matters because `(0)` is just `0` in Python.
    - **Empty tuple** renders as `()`.
    - **Empty frozenset** renders as `frozenset()`, *not* `frozenset({})`
      (which would read as "constructed from an empty dict").
    - Nested tuples: a tuple containing a 1-tuple key should round-trip
      the inner trailing comma too.
    """)
    return


@app.cell
def _():
    # Extra structural tuple edge cases beyond what `composites` shows.
    tuple_edges = {
        (42,): "1-tuple of int — must render with trailing comma",
        ("solo",): "1-tuple of str",
        ((1,), 2): "nested 1-tuple inside a 2-tuple",
    }
    tuple_edges
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 4 — string-escape edge case

    What if a Python **string** key happens to start with `text/plain+`?
    The encoder prefixes it with `text/plain+str:` so it round-trips back
    to the original literal string on the frontend (quoted, as expected).
    Below, four similar-looking entries stay distinct.
    """)
    return


@app.cell
def _():
    lookalike = {
        "text/plain+int:2": "pre-existing string key that looks encoded",
        2: "actual int key",
        "2": "actual string '2'",
        "text/plain+tuple:[1, 2]": "another lookalike",
    }
    lookalike
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 5 — nesting

    Encoding applies recursively at every level. Mixed-key nesting,
    dicts inside lists, and tuples of dicts all walk correctly.
    """)
    return


@app.cell
def _():
    {
        "string key": "ordinary value",
        42: "int key",
        2**100: "bigint key",
        3.14: ["list", "of", "strings"],
        float("inf"): ("tuple", "value"),
        True: {1, 2, 3},
        None: frozenset({"x", "y"}),
        (1, 2): {
            "nested dict": {
                "deep_int": 7,
                (3, 4): "tuple key at depth 2",
                frozenset({"inner"}): ["with", "a", "list"],
            },
            3.0: b"some bytes",
        },
        frozenset({"a", "b"}): [
            {1: "first"},
            {(0, 0): ("origin",)},
        ],
    }
    return


@app.cell
def _():
    in_containers = [
        {1: "a", 2: "b"},
        ({(0, 0): "tuple key"},),
        [
            {None: "None key"},
            {True: "True key", False: "False key"},
        ],
    ]
    in_containers
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 6 — `defaultdict` and `OrderedDict`

    Subclasses and dict-likes should go through the same formatter path.
    """)
    return


@app.cell
def _(defaultdict):
    dd = defaultdict(list)
    dd[1].append("one")
    dd[1].append("also one")
    dd[2.5].append("two-and-a-half")
    dd[(0, 0)].append("origin")
    dd[None].append("none")
    dd
    return


@app.cell
def _(OrderedDict):
    od = OrderedDict([("first", 1), ("second", 2), ("third", 3)])
    od
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 7 — Python-level key collapse (NOT a bug)

    `True == 1 == 1.0` in Python — they hash-equal and collapse into **one**
    dict entry *before* the serializer ever sees it. The first-inserted key
    wins; subsequent assignments only update the value. The output below has
    two entries even though you might expect four.

    This is Python semantics, not a serializer concern; the encoder
    faithfully round-trips what Python actually stored.
    """)
    return


@app.cell
def _():
    collapsed = {}
    collapsed[True] = "first"  # stored as True
    collapsed[1] = "second"  # updates True -> "second"
    collapsed[1.0] = "third"  # still True
    collapsed["distinct"] = "fourth"
    collapsed  # 2 entries total
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 8 — copy-button demo

    Click the **copy** icon next to the rendered dict below. The clipboard
    gets Python-shaped text with unquoted numerics, parens around tuples,
    `frozenset({...})`, `None`/`True`/`False`, and `float('nan')` — ready
    to paste back into code.
    """)
    return


@app.cell
def _():
    copy_target = {
        "plain": "string",
        42: "int",
        3.14: "float",
        float("nan"): "nan",
        float("inf"): "inf",
        -float("inf"): "negative inf",
        True: "true",
        False: "false",
        None: "none",
        (1, 2): "tuple",
        frozenset({"a", "b"}): "frozenset",
        "text/plain+int:99": "escaped lookalike",
    }
    copy_target
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    **Expected clipboard output** (after clicking copy above, modulo JS's
    integer-like-string-key reordering):

    ```python
    {
      "plain": "string",
      42: "int",
      3.14: "float",
      float('nan'): "nan",
      float('inf'): "inf",
      -float('inf'): "negative inf",
      True: "true",
      False: "false",
      None: "none",
      (1, 2): "tuple",
      frozenset({"a", "b"}): "frozenset",
      "text/plain+int:99": "escaped lookalike"
    }
    ```
    """)
    return


if __name__ == "__main__":
    app.run()
