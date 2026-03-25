import marimo

__generated_with = "0.21.1"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    mo.md("""
    ## Password Masking Test (MO-5366)
    """)
    return


@app.cell
def _(mo):
    pw_debounce_true = mo.ui.text(
        kind="password",
        value="secret-B",
        label="debounce=True (default, on blur)",
        debounce=True,
    )
    pw_debounce_true
    return (pw_debounce_true,)


@app.cell
def _(pw_debounce_true):
    print(f"debounce=True value: {pw_debounce_true.value!r}")
    return


@app.cell
def _(mo):
    pw_debounce_num = mo.ui.text(
        kind="password",
        value="secret-C",
        label="debounce=300 (300ms delay)",
        debounce=300,
    )
    pw_debounce_num
    return (pw_debounce_num,)


@app.cell
def _(pw_debounce_num):
    print(f"debounce=300 value: {pw_debounce_num.value!r}")
    return


@app.cell
def _(mo):
    pw_debounce_false = mo.ui.text(
        kind="password",
        value="secret-C",
        label="debounce=False (immediate)",
        debounce=False,
    )
    pw_debounce_false
    return (pw_debounce_false,)


@app.cell
def _(pw_debounce_false):
    print(f"debounce=False value: {pw_debounce_false.value!r}")
    return


@app.cell
def _(mo):
    pw_empty = mo.ui.text(
        kind="password",
        placeholder="No initial value...",
        label="Password (no initial value)",
    )
    pw_empty
    return (pw_empty,)


@app.cell
def _(pw_empty):
    print(f"Empty password value: {pw_empty.value!r}")
    return


if __name__ == "__main__":
    app.run()
