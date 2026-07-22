# Style

Wrap an object in a `<div>` with custom CSS. Pass styles as a dict and/or as
keyword arguments (underscores become hyphens: `max_height` → `max-height`).

/// marimo-embed

```python
@app.cell
def __():
    import marimo as mo
    return

@app.cell
def __():
    mo.style(
        mo.md("This panel scrolls if content overflows."),
        styles={"max-height": "120px", "overflow": "auto", "padding": "0.5rem"},
    )
    return
```

///

::: marimo.style
