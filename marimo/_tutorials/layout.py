# Copyright 2026 Marimo. All rights reserved.
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "marimo",
# ]
# ///

import marimo

__generated_with = "0.25.2"
app = marimo.App()


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    # Layout

    `marimo` provides functions to help you lay out your output, such as
    in rows and columns, accordions, tabs, and callouts.
    """)


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Rows and columns

    Arrange objects into rows and columns with `mo.hstack` and `mo.vstack`.
    """)


@app.cell
def _(mo):
    mo.hstack(
        [mo.ui.text(label="hello"), mo.ui.slider(1, 10, label="slider")],
        justify="start",
    )


@app.cell
def _(mo):
    mo.vstack([mo.ui.text(label="world"), mo.ui.number(1, 10, label="number")])


@app.cell
def _(mo):
    grid = mo.vstack(
        [
            mo.hstack(
                [mo.ui.text(label="hello"), mo.ui.slider(1, 10, label="slider")],
            ),
            mo.hstack(
                [mo.ui.text(label="world"), mo.ui.number(1, 10, label="number")],
            ),
        ],
    ).center()

    mo.md(
        f"""
        Combine `mo.hstack` with `mo.vstack` to make grids:

        {grid}

        You can pass anything to `mo.hstack` to `mo.vstack` (including
        plots!).
        """
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    **Customization.**
    The presentation of stacked elements can be customized with some arguments
    that are best understood by example.
    """)


@app.cell
def _(mo):
    justify = mo.ui.dropdown(
        ["start", "center", "end", "space-between", "space-around"],
        value="space-between",
        label="justify",
    )
    align = mo.ui.dropdown(
        ["start", "center", "end", "stretch"], value="center", label="align"
    )
    gap = mo.ui.number(start=0, step=0.25, stop=2, value=0.5, label="gap")
    wrap = mo.ui.checkbox(label="wrap")

    mo.hstack([justify, align, gap, wrap], justify="center")
    return align, gap, justify, wrap


@app.cell
def _(mo):
    size = mo.ui.slider(label="box size", start=60, stop=500)
    mo.hstack([size], justify="center")
    return (size,)


@app.cell
def _(align, boxes, gap, justify, mo, wrap):
    mo.hstack(
        boxes,
        align=align.value,
        justify=justify.value,
        gap=gap.value,
        wrap=wrap.value,
    )


@app.cell
def _(align, boxes, gap, mo):
    mo.vstack(
        boxes,
        align=align.value,
        gap=gap.value,
    )


@app.cell
def _(mo, size):
    def create_box(num=1):
        box_size = size.value + num * 10
        return mo.Html(
            f"<div style='min-width: {box_size}px; min-height: {box_size}px; background-color: orange; text-align: center; line-height: {box_size}px'>{str(num)}</div>"
        )


    boxes = [create_box(i) for i in range(1, 5)]
    return (boxes,)


@app.cell(hide_code=True)
def _(mo):
    mo.accordion(
        {
            "Documentation: `mo.hstack`": mo.doc(mo.hstack),
            "Documentation: `mo.vstack`": mo.doc(mo.vstack),
        }
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    **Justifying `Html`.** While you can center or right-justify any object
    using `mo.hstack`, `Html` objects (returned by most marimo
    functions, and subclassed by most marimo classes) have a shortcut using
    via their `center`, `right`, and `left` methods.
    """)


@app.cell
def _(mo):
    mo.md("""
    This markdown is left-justified.
    """)


@app.cell
def _(mo):
    mo.md("This markdown is centered.").center()


@app.cell
def _(mo):
    mo.md("This markdown is right-justified.").right()


@app.cell(hide_code=True)
def _(mo):
    mo.accordion(
        {
            "Documentation: `Html.center`": mo.doc(mo.Html.center),
            "Documentation: `Html.right`": mo.doc(mo.Html.right),
            "Documentation: `Html.left`": mo.doc(mo.Html.left),
        }
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Accordion

    Create expandable shelves of content using `mo.accordion`:
    """)


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    An accordion can contain multiple items:
    """)


@app.cell
def _(mo):
    mo.accordion(
        {
            "Multiple items": "By default, only one item can be open at a time",
            "Allow multiple items to be open": (
                """
                Use the keyword argument `multiple=True` to allow multiple items
                to be open at the same time
                """
            ),
        }
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Tabs

    Use `mo.ui.tabs` to display multiple objects in a single tabbed output:
    """)


@app.cell
def _(mo):
    _settings = mo.vstack(
        [
            mo.md("**Edit User**"),
            mo.ui.text(label="First Name"),
            mo.ui.text(label="Last Name"),
        ]
    )

    _organization = mo.vstack(
        [
            mo.md("**Edit Organization**"),
            mo.ui.text(label="Organization Name"),
            mo.ui.number(label="Number of employees", start=0, stop=1000),
        ]
    )

    mo.ui.tabs(
        {
            "🧙‍♀ User": _settings,
            "🏢 Organization": _organization,
        }
    )


@app.cell(hide_code=True)
def _(mo):
    mo.accordion({"Documentation: `mo.ui.tabs`": mo.doc(mo.ui.tabs)})


@app.cell
def _(mo):
    _t = [
        mo.md("**Hello!**"),
        mo.md(r"$f(x)$"),
        {"c": mo.ui.slider(1, 10), "d": (mo.ui.checkbox(), mo.ui.switch())},
    ]

    mo.md(
        f"""
        ## Tree

        Display a nested structure of lists, dictionaries, and tuples with
        `mo.tree`:

        {mo.tree(_t)}
        """
    )


@app.cell(hide_code=True)
def _(mo):
    mo.accordion({"Documentation: `mo.tree`": mo.doc(mo.tree)})


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Callout

    Turn any markdown or HTML into an emphasized callout with the `callout`
    method:
    """)


@app.cell
def _(mo):
    callout_kind = mo.ui.dropdown(
        ["neutral", "warn", "success", "info", "danger"], value="neutral"
    )
    return (callout_kind,)


@app.cell
def _(callout_kind, mo):
    mo.md(
        f"""
        You can turn any HTML or markdown into an emphasized callout.
        You can choose from a variety of callout kinds. This one is:
        {callout_kind}
        """
    ).callout(kind=callout_kind.value, title="This is a callout!")


@app.cell(hide_code=True)
def _(mo):
    mo.accordion({"Documentation: `mo.callout`": mo.doc(mo.callout)})


@app.cell
def _():
    import marimo as mo

    return (mo,)


if __name__ == "__main__":
    app.run()
