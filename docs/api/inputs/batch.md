# Batch

```{eval-rst}
.. marimo-embed::
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

```{eval-rst}
.. autoclass:: marimo.ui.batch
  :members:

  .. autoclasstoc:: marimo._plugins.ui._impl.batch.batch
```
