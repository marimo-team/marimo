# Number

```{eval-rst}
.. marimo-embed::
    @app.cell
    def __():
        number = mo.ui.number(start=1, stop=20, label="Number")
        return

    @app.cell
    def __():
        mo.hstack([number, mo.md(f"Has value: {number.value}")])
        return
```

```{eval-rst}
.. autoclass:: marimo.ui.number
  :members:

  .. autoclasstoc:: marimo._plugins.ui._impl.input.number
```
