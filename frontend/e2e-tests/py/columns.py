# /// script
# [tool.marimo.runtime]
# auto_instantiate = true
# ///
import marimo

__generated_with = "0.0.5"
app = marimo.App(width="columns")


@app.cell(column=0)
def __(deep_and_far_variable, far_away_variable):
    # Two usages, so a find/replace walk has to step through both before it
    # leaves this cell for the definition in column 3 -- the scenario the
    # reporter perceived as search being "stuck" inside a cell.
    usage_of_far_away = far_away_variable + 1
    another_usage = far_away_variable * 2
    usage_of_deep_and_far = deep_and_far_variable + 1
    return (another_usage, usage_of_deep_and_far, usage_of_far_away)


@app.cell(column=1)
def __():
    filler_one = "filler"
    return (filler_one,)


@app.cell(column=2)
def __():
    filler_two = "filler"
    return (filler_two,)


@app.cell(column=3)
def __():
    far_away_variable = 42
    return (far_away_variable,)


@app.cell(column=4)
def __():
    import marimo as mo

    return (mo,)


@app.cell(column=4)
def __(mo):
    # Tall enough to push the cell below into needing a vertical scroll too
    # (viewport height is 720px), unlike far_away_variable, which only ever
    # needs a horizontal scroll.
    mo.ui.text_area(value="filler", rows=80, full_width=True)
    return


@app.cell(column=4)
def __():
    deep_and_far_variable = 99
    return (deep_and_far_variable,)


if __name__ == "__main__":
    app.run()
