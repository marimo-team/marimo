# Checkbox

```{eval-rst}
.. marimo-embed::
    @app.cell
    def __():
        checkbox = mo.ui.checkbox(label="check me")
        return

    @app.cell
    def __():
        mo.hstack([checkbox, mo.md(f"Has value: {checkbox.value}")])
        return
```

```{eval-rst}
.. autoclass:: marimo.ui.checkbox
  :members:

  .. autoclasstoc:: marimo._plugins.ui._impl.input.checkbox
```
