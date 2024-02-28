# Date

```{eval-rst}
.. marimo-embed::
    @app.cell
    def __():
        date = mo.ui.date(label="Start Date")
        return

    @app.cell
    def __():
        mo.hstack([date, mo.md(f"Has value: {date.value}")])
        return
```

```{eval-rst}
.. autoclass:: marimo.ui.date
  :members:

  .. autoclasstoc:: marimo._plugins.ui._impl.input.date
```
