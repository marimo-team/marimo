# Multiselect

```{eval-rst}
.. marimo-embed::
    @app.cell
    def __():
        options = ["Apples", "Oranges", "Pears"]
        multiselect = mo.ui.multiselect(options=options)
        return

    @app.cell
    def __():
        mo.hstack([multiselect, mo.md(f"Has value: {multiselect.value}")])
        return
```

```{eval-rst}
.. autoclass:: marimo.ui.multiselect
  :members:

  .. autoclasstoc:: marimo._plugins.ui._impl.input.multiselect
```
