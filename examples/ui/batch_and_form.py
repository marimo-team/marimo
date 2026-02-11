# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "marimo",
# ]
# ///

import marimo

__generated_with = "0.19.7"
app = marimo.App()


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    mo.md("""
    # Batch and Form
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    Make custom UI elements using `batch()`, and turn any UI element
    into a form with `form()`.
    """)
    return


@app.cell
def _(mo, reset):
    reset

    variables = (
        mo.md(
            """
            Choose your variable values

            {x}

            {y}
            """
        )
        .batch(
            x=mo.ui.slider(start=1, stop=10, step=1, label="$x =$"),
            y=mo.ui.slider(start=1, stop=10, step=1, label="$y =$"),
        )
        .form(show_clear_button=True, bordered=False)
    )

    variables
    return (variables,)


@app.cell
def _(mo, reset, submitted_values, variables):
    if variables.value is not None:
        submitted_values["x"].add(variables.value["x"])
        submitted_values["y"].add(variables.value["y"])

    x = variables.value["x"] if variables.value else r"\ldots"
    y = variables.value["y"] if variables.value else r"\ldots"


    mo.md(
        f"""
        At the moment,
        $x = {x}$ and $y = {y}$

        All values ever assumed by $x$ and $y$ are

        {mo.hstack([mo.tree(submitted_values), reset], align="center", gap=4)}
        """
    ).callout()
    return


@app.cell
def _(reset):
    reset

    submitted_values = {"x": set(), "y": set()}
    return (submitted_values,)


@app.cell
def _(mo):
    reset = mo.ui.button(label="reset history")
    return (reset,)


if __name__ == "__main__":
    app.run()
