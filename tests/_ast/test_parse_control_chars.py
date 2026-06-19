# Copyright 2026 Marimo. All rights reserved.
"""Regression tests: control characters in cell source must not crash parsing.

These reproduce real notebooks that marimo *itself generated* (note the
`__generated_with` header) but could no longer parse back — a round-trip bug.

Root cause: a form-feed (`\\x0c`, e.g. produced when a LaTeX `\\frac` in a
markdown string is written without escaping) embedded in a cell's source
corrupts the line/column offset arithmetic in `Parser.extract_from_code`. As a
result `extract_offsets_post_colon` is handed a fragment of a *later* cell's
`@app.cell` decorator instead of the cell's own `def` block. That fragment then
crashes:

- with a bare `AssertionError` at `parse.py:extract_offsets_post_colon`
  (`assert def_node is not None`) when the fragment contains no `def` token, or
- with a `tokenize.TokenError` when a control character / unbalanced `(` from a
  parametrized `@app.cell(...)` decorator makes the fragment untokenizable.

Both crash `marimo check` (and any deserialize path: editor open, convert, run)
with an unhandled traceback instead of degrading gracefully.

TDD: these assert the *desired* graceful behavior and fail until the parser is
hardened to either record a violation or raise a well-defined, catchable error.
"""

from __future__ import annotations

import tokenize

import pytest

from marimo._ast.parse import parse_notebook

# A form-feed (\x0c) inside an `mo.md` string. The tabs (\t, shown as `\times`
# in the literal) come from an unescaped LaTeX `\times`. marimo generated this
# file but, today, asserts out when parsing it back.
NOTEBOOK_FORMFEED_ASSERT = 'import marimo\n__generated_with = "0.17.7"\napp = marimo.App(\n)\n@app.cell\ndef _(mo):\n    mo.md("""\n    P=\x0c    rac{TP}{TP+FP}\n    R=\x0c    rac{TP}{TP+FN}\n    F1 = \x0c    rac{2\times P\times R}{P+R}\n    """)\n    return\n\n@app.cell\ndef _(mo):\n    mo.md("""\n    """)\n    return\n\n@app.cell\ndef _():\n    pass\n    return\nif __name__ == "__main__":\n    app.run()\n'

# Same root cause; parametrized `@app.cell(hide_code=True)` decorators make the
# mis-extracted fragment untokenizable -> tokenize.TokenError instead.
NOTEBOOK_FORMFEED_TOKEN = 'import marimo\n__generated_with = "0.17.4"\napp = marimo.App(width="medium", auto_download=["html"])\n@app.cell(hide_code=True)\ndef _(mo):\n    mo.md("""\n    P=\x0c    rac{TP}{TP+FP}\n    R=\x0c    rac{TP}{TP+FN}\n    F1 = \x0c    rac{2\times P\times R}{P+R}\n    """)\n    return\n@app.cell(hide_code=True)\ndef _(mo):\n    mo.md("""\n\n    **Interpret your results**\n    """)\n    return\n@app.cell(hide_code=True)\ndef _(mo):\n    mo.md("""My answer:""")\n    return\nif __name__ == "__main__":\n    app.run()\n'


def test_fixtures_actually_contain_control_chars() -> None:
    # Guard: these fixtures are only meaningful if the control chars survive.
    assert "\x0c" in NOTEBOOK_FORMFEED_ASSERT
    assert "\x0c" in NOTEBOOK_FORMFEED_TOKEN
    assert "\t" in NOTEBOOK_FORMFEED_ASSERT


def test_formfeed_in_cell_string_does_not_assert() -> None:
    # Today: AssertionError at parse.py extract_offsets_post_colon.
    notebook = parse_notebook(NOTEBOOK_FORMFEED_ASSERT)
    assert notebook is not None


def test_control_chars_do_not_raise_tokenerror() -> None:
    # Today: tokenize.TokenError while parsing the notebook.
    notebook = parse_notebook(NOTEBOOK_FORMFEED_TOKEN)
    assert notebook is not None


@pytest.mark.parametrize(
    "source",
    [NOTEBOOK_FORMFEED_ASSERT, NOTEBOOK_FORMFEED_TOKEN],
    ids=["assert_case", "token_case"],
)
def test_parse_notebook_never_crashes_on_control_chars(source: str) -> None:
    # The contract: malformed/odd input yields a NotebookSerialization (which
    # may carry `.violations`), never an unhandled AssertionError/TokenError.
    try:
        notebook = parse_notebook(source)
    except (AssertionError, tokenize.TokenError) as e:
        pytest.fail(
            f"parse_notebook crashed on control chars: {type(e).__name__}: {e}"
        )
    assert notebook is not None


@pytest.mark.parametrize(
    "source",
    [NOTEBOOK_FORMFEED_ASSERT, NOTEBOOK_FORMFEED_TOKEN],
    ids=["assert_case", "token_case"],
)
def test_marimo_check_does_not_crash_on_control_chars(
    source: str, tmp_path
) -> None:
    # `marimo check` must report a diagnostic / file error, not die with a
    # traceback. run_check should return a Linter even for broken notebooks.
    from marimo._lint import run_check

    nb = tmp_path / "notebook.py"
    nb.write_text(source)

    try:
        result = run_check((str(nb),))
    except (AssertionError, tokenize.TokenError) as e:
        pytest.fail(
            f"`marimo check` crashed on control chars: {type(e).__name__}: {e}"
        )
    assert result is not None
    assert len(result.files) == 1
