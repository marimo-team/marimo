# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.23.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    # `.center()` / `.left()` / `.right()` smoke tests

    This notebook exercises the Html alignment helpers across a variety
    of content types. Scroll through the cells to visually confirm each
    scenario.

    **Expected behavior**

    - `.center()` horizontally centers the content as a block unit.
    - `.left()` and `.right()` align the content to the respective edge
      at its natural (content) width.
    - **Newlines / multi-block markdown must be preserved** (this was
      the original bug: headings + paragraphs were being flattened
      into a horizontal row).
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## 1. Single-line markdown
    """)
    return


@app.cell
def _(mo):
    mo.md("This markdown is **centered**.").center()
    return


@app.cell
def _(mo):
    mo.md("This markdown is **left**-justified.").left()
    return


@app.cell
def _(mo):
    mo.md("This markdown is **right**-justified.").right()
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## 2. Multi-block markdown (the original bug)

    The heading and paragraph must stack **vertically**, each
    horizontally aligned according to the method called.
    """)
    return


@app.cell
def _(mo):
    mo.md(
        """
        # Centered title

        A deck exercising slides, sub-slides (stacks), fragments, and skip cells.
        """
    ).center()
    return


@app.cell
def _(mo):
    mo.md(
        """
        # Left-aligned title

        A description that should appear on its own line, left-aligned.
        """
    ).left()
    return


@app.cell
def _(mo):
    mo.md(
        """
        # Left-aligned title

        A description that should appear on its own line, left-aligned.
        """
    ).left().style({"height": "80px", "overflow": "auto", "background": "lightgray"})
    return


@app.cell
def _(mo):
    mo.md(
        """
        # Right-aligned title

        A description that should appear on its own line, right-aligned.
        """
    ).right()
    return


@app.cell
def _(mo):
    mo.md(
        """
        ## Heading

        First paragraph of several lines of prose that should
        wrap naturally and stay as its own block.

        Second paragraph, also on its own block-level line.

        - A list item
        - Another list item
        """
    ).center()
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## 3. Single UI element
    """)
    return


@app.cell
def _(mo):
    mo.ui.button(label="Centered button").center()
    return


@app.cell
def _(mo):
    mo.ui.button(label="Left button").left()
    return


@app.cell
def _(mo):
    mo.ui.button(label="Right button").right()
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## 4. Inline UI inside markdown
    """)
    return


@app.cell
def _(mo):
    _button = mo.ui.button(label="Click me")
    mo.md(f"{_button} _inline button with text, centered as a line._").center()
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## 5. Images
    """)
    return


@app.cell
def _(mo):
    mo.image(
        src="https://marimo.io/logo.png",
        width=120,
    ).center()
    return


@app.cell
def _(mo):
    mo.md(
        "![marimo](https://marimo.io/logo.png)\n\n*A caption below the image.*"
    ).center()
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## 6. Alignment applied to an `hstack`

    `.left()` / `.center()` / `.right()` group the hstack at the
    requested edge at its content width.
    """)
    return


@app.cell
def _(mo):
    mo.hstack(
        [
            mo.ui.checkbox(label="A"),
            mo.ui.checkbox(label="B"),
            mo.ui.checkbox(label="C"),
        ],
        gap=1,
    ).left()
    return


@app.cell
def _(mo):
    mo.hstack(
        [
            mo.ui.checkbox(label="A"),
            mo.ui.checkbox(label="B"),
            mo.ui.checkbox(label="C"),
        ],
        gap=1,
    ).center()
    return


@app.cell
def _(mo):
    mo.hstack(
        [
            mo.ui.checkbox(label="A"),
            mo.ui.checkbox(label="B"),
            mo.ui.checkbox(label="C"),
        ],
        gap=1,
    ).right()
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## 7. Alignment applied to a `vstack`
    """)
    return


@app.cell
def _(mo):
    mo.vstack(
        [
            mo.md("**Title**"),
            mo.md("A short paragraph below the title."),
            mo.ui.button(label="Action"),
        ],
        gap=0.5,
    ).center()
    return


@app.cell
def _(mo):
    mo.vstack(
        [
            mo.md("**Title**"),
            mo.md("A short paragraph below the title."),
            mo.ui.button(label="Action"),
        ],
        gap=0.5,
    ).right()
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## 8. Chained with `.callout()`

    Newlines inside the markdown must be preserved inside the callout.
    """)
    return


@app.cell
def _(mo):
    mo.md(
        """
        # Important notice

        The callout body should render with this heading on its own line
        and this paragraph on the following line.
        """
    ).center().callout(kind="info")
    return


@app.cell
def _(mo):
    mo.md(
        """
        # Warning

        Multiple paragraphs.

        All left-aligned and stacked vertically.
        """
    ).left().callout(kind="warn")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## 9. Module-level helpers

    `mo.center(x)`, `mo.left(x)`, `mo.right(x)` should behave
    identically to the `.center()` / `.left()` / `.right()` methods.
    """)
    return


@app.cell
def _(mo):
    mo.center(
        mo.md(
            """
            # Module-level center

            Heading + paragraph, still stacked vertically.
            """
        )
    )
    return


@app.cell
def _(mo):
    mo.left(mo.ui.button(label="mo.left(button)"))
    return


@app.cell
def _(mo):
    mo.right(mo.ui.button(label="mo.right(button)"))
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## 10. Double-chained alignment

    Last call wins; newlines still preserved.
    """)
    return


@app.cell
def _(mo):
    mo.md(
        """
        # Double-chain

        First centered, then left-aligned -- should end up left-aligned
        with block flow intact.
        """
    ).center().left()
    return


if __name__ == "__main__":
    app.run()
