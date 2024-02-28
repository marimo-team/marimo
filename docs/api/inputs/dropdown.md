# Dropdown

```{eval-rst}
.. marimo-embed::
    @app.cell
    def __():
        options = ["Apples", "Oranges", "Pears"]
        dropdown = mo.ui.dropdown(options=options)
        return

    @app.cell
    def __():
        mo.hstack([dropdown, mo.md(f"Has value: {dropdown.value}")])
        return
```

```{eval-rst}
.. autoclass:: marimo.ui.dropdown
  :members:

  .. autoclasstoc:: marimo._plugins.ui._impl.input.dropdown
```
