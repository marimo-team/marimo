# Batch

/// marimo-embed

```python
    @app.cell
    def __():
        el = mo.md("{start} → {end}").batch(
            start=mo.ui.date(label="Start Date"),
            end=mo.ui.date(label="End Date")
        )
        el
        return

    @app.cell
    def __():
        el.value
        return
```

///

::: marimo.ui.batch
