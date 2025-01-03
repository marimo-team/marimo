# Button

!!! tip "Looking for a submit/run button?"
    If you're looking for a button to trigger computation on click, consider
    using [`mo.ui.run_button`][marimo.ui.run_button].

/// marimo-embed

```python
@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _(mo):
    button = mo.ui.button(
        value=0, on_click=lambda value: value + 1, label="increment", kind="warn"
    )
    button
    return (button,)


@app.cell
def _(button):
    button.value
    return
```

///

::: marimo.ui.button
