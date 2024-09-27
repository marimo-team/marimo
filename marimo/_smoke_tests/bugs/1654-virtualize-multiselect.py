# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.8.20"
app = marimo.App(app_title="1654 - Virtualize Multiselect")


@app.cell
def __():
    import marimo as mo
    return (mo,)


@app.cell
def __(mo):
    fuzzy_match_test = ["foo bar", "bar foo", "foob", "foobar", "barfoo"]
    mo.ui.multiselect(fuzzy_match_test, label="Fuzzy match test")
    return (fuzzy_match_test,)


@app.cell
def __(mo):
    (
        mo.ui.multiselect([], label="Empty"),
        mo.ui.multiselect(["1", "2"], label="2 items"),
    )
    return


@app.cell
def __(mo, xs_list):
    v = mo.ui.multiselect(xs_list, label="Extra small list with 10 items")
    v
    return (v,)


@app.cell
def __(v):
    print(v.value)
    return


@app.cell
def __(mo, sm_list):
    mo.ui.multiselect(sm_list, label="Small list with 100 items")
    return


@app.cell
def __(md_list, mo):
    mo.ui.multiselect(md_list, label="Medium list with 500 items")
    return


@app.cell
def __(lg_list, mo):
    mo.ui.multiselect(lg_list, label="Large list with 1K items")
    return


@app.cell
def __(mo, xl_list):
    mo.ui.multiselect(xl_list, label="XL list with 10K items")
    return


@app.cell
def __(mo, xxl_list):
    mo.ui.multiselect(xxl_list, label="XXL list with 100K items")
    return


@app.cell
def __(mo, xxxl_list):
    try:
        mo.ui.multiselect(xxxl_list, label="XXXL list with 200K items")
    except ValueError as e:
        print(e)
    return


@app.cell
def __():
    RANGE = 10000
    xs_list = [f"Row {i}" for i in range(RANGE // 1000)]
    sm_list = [f"Row {i}" for i in range(RANGE // 100)]
    md_list = [f"Row {i}" for i in range(RANGE // 20)]
    lg_list = [f"Row {i}" for i in range(RANGE // 10)]
    xl_list = [f"Row {i}" for i in range(RANGE)]
    xxl_list = [f"Row {i}" for i in range(RANGE * 10)]
    xxxl_list = [f"Row {i}" for i in range(RANGE * 20)]
    return (
        RANGE,
        lg_list,
        md_list,
        sm_list,
        xl_list,
        xs_list,
        xxl_list,
        xxxl_list,
    )


if __name__ == "__main__":
    app.run()
