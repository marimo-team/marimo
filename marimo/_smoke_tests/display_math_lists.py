# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.24.0"
app = marimo.App()


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _(mo):
    mo.md("""
    # Display math in lists

    Check that equations and following text stay inside their list items.
    The numbered list should have three items.
    """)
    return


@app.cell
def _(mo):
    mo.md(r"""
    1. First item.
    2. Inline $a^2$ and display math:
       $$
       E = mc^2
       $$
       This text belongs to item two.
    3. Third item.
    """)
    return


@app.cell
def _(mo):
    mo.vstack([
        mo.md(
            f"{_marker} First item.\n"
            f"{_marker} Display math:\n"
            "  $$x^2 + y^2 = z^2$$\n"
            "  This text belongs to the second bullet.\n"
            f"{_marker} Third item."
        )
        for _marker in ["-", "*", "+"]
    ])
    return


@app.cell
def _(mo):
    mo.md("""
    ## Horizontal rules

    Each separator below should be followed by ordinary text, with no code
    block. Display math at this indentation still has a pre-existing rendering
    issue; this check only verifies that the content does not become code.
    """)
    return


@app.cell
def _(mo):
    mo.vstack([
        mo.md(
            f"Separator `{_rule}`:\n\n"
            f"{_rule}\n"
            "  $$x$$\n"
            "  This should remain prose.\n\n"
            "End of example."
        )
        for _rule in ["- - -", "* * *", "- --", "* **"]
    ])
    return


@app.cell
def _(mo):
    mo.md("""
    ## Mixed indentation

    The equation and following text should stay inside the first item.

    - First item
      continued here:
        $$x$$
      Text after the equation.
    - Second item.
    """)
    return


if __name__ == "__main__":
    app.run()
