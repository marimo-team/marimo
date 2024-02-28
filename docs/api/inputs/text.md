# Text

```{eval-rst}
.. marimo-embed::
    @app.cell
    def __():
        text = mo.ui.text(placeholder="Search...", label="Filter")
        return

    @app.cell
    def __():
        mo.hstack([text, mo.md(f"Has value: {text.value}")])
        return
```

```{eval-rst}
.. autoclass:: marimo.ui.text
  :members:

  .. autoclasstoc:: marimo._plugins.ui._impl.input.text
```
