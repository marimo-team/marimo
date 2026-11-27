# Copyright 2026 Marimo. All rights reserved.
"""Regression tests: control characters in cell source must not crash parsing.

These reproduce real notebooks that marimo *itself generated* (note the
`__generated_with` header) but could no longer parse back — a round-trip bug.
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
# incorrectly extracted fragment untokenizable -> tokenize.TokenError instead.
NOTEBOOK_FORMFEED_TOKEN = 'import marimo\n__generated_with = "0.17.4"\napp = marimo.App(width="medium", auto_download=["html"])\n@app.cell(hide_code=True)\ndef _(mo):\n    mo.md("""\n    P=\x0c    rac{TP}{TP+FP}\n    R=\x0c    rac{TP}{TP+FN}\n    F1 = \x0c    rac{2\times P\times R}{P+R}\n    """)\n    return\n@app.cell(hide_code=True)\ndef _(mo):\n    mo.md("""\n\n    **Interpret your results**\n    """)\n    return\n@app.cell(hide_code=True)\ndef _(mo):\n    mo.md("""My answer:""")\n    return\nif __name__ == "__main__":\n    app.run()\n'


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


def test_control_chars_preserved_across_ast_and_lint_helpers() -> None:
    from marimo._ast.codegen import build_setup_section
    from marimo._ast.compiler import cache
    from marimo._ast.parse import split_source_lines_keepends
    from marimo._ast.scanner import _extract_body_code, scan_notebook
    from marimo._lint.context import LintContext
    from marimo._lint.rules.formatting.empty_cells import EmptyCellRule

    # Form-feed (\x0c) and Unicode line separator (\u2028) must not split lines.
    assert split_source_lines_keepends("a\x0cb\u2028c\nd\r\ne") == [
        "a\x0cb\u2028c\n",
        "d\r\n",
        "e",
    ]
    assert split_source_lines_keepends("") == []

    # Fallback scanner recovers cell without corrupting line offsets when \x0c appears before a syntax error.
    malformed = '@app.cell\ndef _():\n    x = "a\x0cb"\n    (\n'
    scan = scan_notebook(malformed)
    assert len(scan.cells) == 1
    assert 'x = "a\x0cb"' in _extract_body_code(malformed, "cell")

    # Compiler linecache keeps exact Python line count.
    cache("<test_control_char>", 'x = "a\x0cb"\ny = 1')

    # LintContext & EmptyCellRule agree with AST line counts on \x0c / \u2028.
    ctx = LintContext(notebook=parse_notebook(NOTEBOOK_FORMFEED_ASSERT), contents=NOTEBOOK_FORMFEED_ASSERT)
    assert ctx.contents[0] == "import marimo"
    assert EmptyCellRule()._is_only_comments('# comment\x0cstill comment\n# line2')

    setup = parse_notebook('import marimo\napp = marimo.App()\nwith app.setup:\n    # a\x0cb\n    x = 1\n').cells[0]
    from marimo._ast.compiler import compile_cell
    setup_cell = compile_cell(setup.code, cell_id="setup")
    assert "with app.setup:" in build_setup_section(setup_cell)
