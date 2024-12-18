# Text

/// marimo-embed

```python
@app.cell
def __():
    text = mo.ui.text(placeholder="Search...", label="Filter")
    return

@app.cell
def __():
    mo.hstack([text, mo.md(f"Has value: {text.value}")])
    return
```

///

::: marimo.ui.text
