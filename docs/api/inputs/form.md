# Form

{{ create_marimo_embed("""

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

""", size="medium") }}

::: marimo.ui.form
