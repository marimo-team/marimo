# Multiselect

/// marimo-embed

```python
@app.cell
def __():
    options = ["Apples", "Oranges", "Pears"]
    multiselect = mo.ui.multiselect(options=options)
    return

@app.cell
def __():
    mo.hstack([multiselect, mo.md(f"Has value: {multiselect.value}")])
    return
```

///

::: marimo.ui.multiselect
