# Run Button

/// marimo-embed
    size: medium

```python
@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _(mo):
    b = mo.ui.run_button()
    b
    return (b,)


@app.cell
def _(mo):
    s = mo.ui.slider(1, 10)
    s
    return (s,)


@app.cell
def _(b, mo, s):
    mo.stop(not b.value, "Click `run` to submit the slider's value")
    s.value
    return
```

///

::: marimo.ui.run_button
