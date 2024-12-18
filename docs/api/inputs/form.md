# Form

/// marimo-embed
    size: medium

```python
@app.cell
def __():
    form = mo.ui.text_area(placeholder="...").form()
    return

@app.cell
def __():
    mo.vstack([form, mo.md(f"Has value: {form.value}")])
    return
```

///

::: marimo.ui.form
