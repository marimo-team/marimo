import marimo

__generated_with = "0.1.0"
app = marimo.App()


@app.cell
def __(mo):
    mo.md("# Batch and Form")
    return


@app.cell
def __(mo):
    mo.md(
        """
        Make custom UI elements using `batch()`, and turn any UI element
        into a form with `form()`.
        """
    )
    return


@app.cell
def __(mo, reset):
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
        .form()
    )

    variables
    return variables,


@app.cell
def __(mo, reset, submitted_values, variables):
    if variables.value is not None:
        submitted_values["x"].add(variables.value["x"])
        submitted_values["y"].add(variables.value["y"])

    x = variables.value["x"] if variables.value else "\ldots"
    y = variables.value["y"] if variables.value else "\ldots"


    mo.md(
        f"""
        At the moment,
        $x = {x}$ and $y = {y}$

        All values ever assumed by $x$ and $y$ are

        {mo.hstack([mo.tree(submitted_values), reset],
                   justify="start", align="center", gap=4)}
        """
    ).callout()
    return x, y


@app.cell
def __(reset):
    reset

    submitted_values = {
        "x": set(),
        "y": set()
    }
    return submitted_values,


@app.cell
def __(mo):
    reset = mo.ui.button(label="reset history")
    return reset,


@app.cell
def __():
    import marimo as mo
    return mo,


if __name__ == "__main__":
    app.run()
