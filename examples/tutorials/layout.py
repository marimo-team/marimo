# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.1.69"
app = marimo.App()


@app.cell(hide_code=True)
def __(mo):
    mo.md(
        """
        # Layout

        `marimo` provides functions to help you lay out your output, such as
        in rows and columns, accordions, tabs, and callouts.
        """
    )
    return


@app.cell(hide_code=True)
def __(mo):
    mo.md(
        """
        ## Rows and columns

        Arrange objects into rows and columns with `mo.hstack` and `mo.vstack`.
        """
    )
    return


@app.cell
def __(mo):
    mo.hstack(
        [mo.ui.text(label="hello"), mo.ui.slider(1, 10, label="slider")],
        justify="start",
    )
    return


@app.cell
def __(mo):
    mo.vstack([mo.ui.text(label="world"), mo.ui.number(1, 10, label="number")])
    return


@app.cell
def __(mo):
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
    return grid,


@app.cell(hide_code=True)
def __(mo):
    mo.md(
        """
        **Customization.**
        The presentation of stacked elements can be customized with some arguments
        that are best understood by example.
        """
    )
    return


@app.cell
def __(mo):
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
def __(mo):
    size = mo.ui.slider(label="box size", start=60, stop=500)
    mo.hstack([size], justify="center")
    return size,


@app.cell
def __(align, boxes, gap, justify, mo, wrap):
    mo.hstack(
        boxes,
        align=align.value,
        justify=justify.value,
        gap=gap.value,
        wrap=wrap.value,
    )
    return


@app.cell
def __(align, boxes, gap, mo):
    mo.vstack(
        boxes,
        align=align.value,
        gap=gap.value,
    )
    return


@app.cell
def __(mo, size):
    def create_box(num=1):
        box_size = size.value + num * 10
        return mo.Html(
            f"<div style='min-width: {box_size}px; min-height: {box_size}px; background-color: orange; text-align: center; line-height: {box_size}px'>{str(num)}</div>"
        )


    boxes = [create_box(i) for i in range(1, 5)]
    return boxes, create_box


@app.cell(hide_code=True)
def __(mo):
    mo.accordion(
        {
            "Documentation: `mo.hstack`": mo.doc(mo.hstack),
            "Documentation: `mo.vstack`": mo.doc(mo.vstack),
        }
    )
    return


@app.cell(hide_code=True)
def __(mo):
    mo.md(
        """
        **Justifying `Html`.** While you can center or right-justify any object
        using `mo.hstack`, `Html` objects (returned by most marimo
        functions, and subclassed by most marimo classes) have a shortcut using
        via their `center`, `right`, and `left` methods.
        """
    )
    return


@app.cell
def __(mo):
    mo.md("This markdown is left-justified.")
    return


@app.cell
def __(mo):
    mo.md("This markdown is centered.").center()
    return


@app.cell
def __(mo):
    mo.md("This markdown is right-justified.").right()
    return


@app.cell(hide_code=True)
def __(mo):
    mo.accordion(
        {
            "Documentation: `Html.center`": mo.doc(mo.Html.center),
            "Documentation: `Html.right`": mo.doc(mo.Html.right),
            "Documentation: `Html.left`": mo.doc(mo.Html.left),
        }
    )
    return


@app.cell(hide_code=True)
def __(mo):
    mo.md(
        """
        ## Accordion

        Create expandable shelves of content using `mo.accordion`:
        """
    )
    return


@app.cell(hide_code=True)
def __(mo):
    mo.md(
        """
        An accordion can contain multiple items:
        """
    )
    return


@app.cell
def __(mo):
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
    return


@app.cell(hide_code=True)
def __(mo):
    mo.md(
        """
        ## Tabs

        Use `mo.ui.tabs` to display multiple objects in a single tabbed output:
        """
    )
    return


@app.cell
def __(mo):
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
    return


@app.cell(hide_code=True)
def __(mo):
    mo.accordion({"Documentation: `mo.ui.tabs`": mo.doc(mo.ui.tabs)})
    return


@app.cell
def __(mo):
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
    return


@app.cell(hide_code=True)
def __(mo):
    mo.accordion({"Documentation: `mo.tree`": mo.doc(mo.tree)})
    return


@app.cell(hide_code=True)
def __(mo):
    mo.md(
        """
        ## Callout

        Turn any markdown or HTML into an emphasized callout with the `callout`
        method:
        """
    )
    return


@app.cell
def __(mo):
    callout_kind = mo.ui.dropdown(
        ["neutral", "warn", "success", "info", "danger"], value="neutral"
    )
    return callout_kind,


@app.cell
def __(callout_kind, mo):
    mo.md(
        f"""
        **This is a callout!**

        You can turn any HTML or markdown into an emphasized callout.
        You can choose from a variety of different callout kind. This one is:
        {callout_kind}
        """
    ).callout(kind=callout_kind.value)
    return


@app.cell(hide_code=True)
def __(mo):
    mo.accordion({"Documentation: `mo.callout`": mo.doc(mo.callout)})
    return


@app.cell
def __():
    import marimo as mo
    return mo,


if __name__ == "__main__":
    app.run()
