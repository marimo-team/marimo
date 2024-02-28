# Text Area

```{eval-rst}
.. marimo-embed::
    @app.cell
    def __():
        text_area = mo.ui.text_area(placeholder="Search...", label="Description")
        return

    @app.cell
    def __():
        mo.hstack([text_area, mo.md(f"Has value: {text_area.value}")])
        return
```

```{eval-rst}
.. autoclass:: marimo.ui.text_area
  :members:

  .. autoclasstoc:: marimo._plugins.ui._impl.input.text_area
```
