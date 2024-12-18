# Radio

/// marimo-embed

```python
@app.cell
def __():
    options = ["Apples", "Oranges", "Pears"]
    radio = mo.ui.radio(options=options)
    return

@app.cell
def __():
    mo.hstack([radio, mo.md(f"Has value: {radio.value}")])
    return
```

///

::: marimo.ui.radio
