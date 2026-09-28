import marimo

__generated_with = "0.24.0"
app = marimo.App(width="medium")


@app.cell
def _():
    import json

    import marimo as mo

    return json, mo


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    # JSON viewer smoke test

    Based on [PR #10865](https://github.com/marimo-team/marimo/pull/10865).
    Repeat these checks in light and dark mode. Use Tab to focus controls,
    then Enter or Space to expand nodes, reveal long strings, and copy values.
    Paste copied values into a text editor to check their contents.

    ## JSON versus Python

    JSON should show `true`, `false`, and `null`; Python should show
    `True`, `False`, and `None`. MIME-looking strings must remain literal
    text in JSON mode. Expand the long string and check quotes and wrapping.
    """)
    return


@app.cell
def _():
    sample = {
        "text": 'Quotes: "hello"; backslash: \\; newline:\nnext line',
        "unicode": "こんにちは · café · 🐍",
        "enabled": True,
        "disabled": False,
        "missing": None,
        "numbers": [0, -7, 3.14159],
        "empty": {"object": {}, "array": [], "string": ""},
        "long": "Expand me! " * 25 + "END OF STRING",
        "mime_strings": ["text/plain:literal", "text/html:<b>literal</b>"],
    }
    return (sample,)


@app.cell
def _(mo, sample):
    mo.json(sample, label="JSON values")
    return


@app.cell
def _(sample):
    sample
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Python types and rich leaves

    Check tuples (including a singleton), sets, large integers, special floats,
    and non-string keys. Copies should preserve Python literal syntax.
    HTML and Markdown leaves should render inline without a leaf copy button.
    """)
    return


@app.cell
def _(mo):
    {
        "tuple": (1, True, None),
        "singleton": ("only",),
        "set": {1, 2, 3},
        "empty_set": set(),
        "frozen": frozenset({"a", "b"}),
        "big_integer": 2**80,
        "special_floats": [float("nan"), float("inf"), -float("inf")],
        "keys": {42: "integer", None: "none", (1, 2): "tuple"},
        "html": mo.Html("<strong>Rich HTML leaf</strong>"),
        "markdown": mo.md("**Rich Markdown leaf**"),
    }
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Pagination, counts, and copies

    Each collection has **65 items**. Initially expect 30 visible entries and
    **35 more items**; after one click, **5 more items**; after another, no
    pagination button. Counts must stay at 65. Copy the root before expanding:
    both collections must include every entry through index 64.

    Expanding `a.b` must not change pagination for `a` → `b`, or vice versa.
    Empty keys and `__proto__` must remain visible as ordinary data keys.
    """)
    return


@app.cell
def _(mo):
    mo.json(
        {
            "a.b": list(range(65)),
            "a": {"b": list(range(100, 165))},
            "object": {f"key_{i:02}": i for i in range(65)},
            "": "empty key",
            "__proto__": {"safe": True},
        },
        label="Independent pagination",
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Matrix pagination and deep nesting

    The 12 × 60 matrix should start with 5 rows and 5 items per row.
    Copying it must include all 720 values. Expand the deep tree manually;
    deeper levels should start collapsed and remain accessible.
    """)
    return


@app.cell
def _(mo):
    mo.json([[row * 100 + col for col in range(60)] for row in range(12)])
    return


@app.cell
def _(mo):
    _tree = {"leaf": "Reached the bottom"}
    for _level in range(8, 0, -1):
        _tree = {f"level_{_level}": _tree}
    mo.json(_tree)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Root values and JSON strings

    Empty containers and scalar JSON roots should render without errors.
    JSON text passed to `mo.json` should parse into a tree.
    """)
    return


@app.cell
def _(mo):
    mo.vstack(
        [
            mo.json({}, label="Empty object"),
            mo.json([], label="Empty array"),
            mo.json("null"),
            mo.json("true"),
            mo.json("42"),
            mo.json('"hello"'),
            mo.json('{"parsed": [true, null, {"nested": 1}]}'),
        ]
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Table popovers and inspector

    Open the object, array, and JSON-string cells. Check expansion, copying,
    and theme colors in each popover. The plain string should remain text.
    The inspector should use consistent string colors.
    """)
    return


@app.cell
def _(json, mo, sample):
    mo.ui.table(
        [
            {
                "object": sample,
                "array": list(range(65)),
                "json_string": json.dumps(sample),
                "plain_string": "This is not JSON",
            }
        ],
        selection=None,
    )
    return


@app.cell
def _(mo):
    from types import SimpleNamespace

    mo.inspect(SimpleNamespace(name="Inspector string", values=[1, True, None]))
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Plugin error details (intentional)

    The next output deliberately supplies an invalid plugin option. Expect a
    **Bad Data** alert. Open **View Data** and check that its JSON tree works.
    This is an expected frontend validation error, not a Python cell failure.
    """)
    return


@app.cell
def _(mo):
    from marimo._plugins.core.web_component import build_stateless_plugin

    mo.Html(
        build_stateless_plugin(
            component_name="marimo-json-output",
            args={
                "json-data": {"message": "Intentional invalid value-types"},
                "value-types": "invalid-smoke-test-mode",
            },
        )
    )
    return


if __name__ == "__main__":
    app.run()
