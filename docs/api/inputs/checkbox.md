# Checkbox

/// marimo-embed

```python
@app.cell
def __():
    checkbox = mo.ui.checkbox(label="check me")
    return

@app.cell
def __():
    mo.hstack([checkbox, mo.md(f"Has value: {checkbox.value}")])
    return
```

///

::: marimo.ui.checkbox
