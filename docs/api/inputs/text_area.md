# Text Area

/// marimo-embed

```python
@app.cell
def __():
    text_area = mo.ui.text_area(placeholder="Search...", label="Description")
    return

@app.cell
def __():
    mo.hstack([text_area, mo.md(f"Has value: {text_area.value}")])
    return///

::: marimo.ui.text_area
```
