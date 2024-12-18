# Number

/// marimo-embed

```python
@app.cell
def __():
    number = mo.ui.number(start=1, stop=20, label="Number")
    return

@app.cell
def __():
    mo.hstack([number, mo.md(f"Has value: {number.value}")])
    return
```

///

::: marimo.ui.number
