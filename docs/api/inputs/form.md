# Form

```{eval-rst}
.. marimo-embed::
    :size: medium

    @app.cell
    def __():
        form = mo.ui.text_area(placeholder="...").form()
        return

    @app.cell
    def __():
        mo.vstack([form, mo.md(f"Has value: {form.value}")])
        return
```

```{eval-rst}
.. autoclass:: marimo.ui.form
  :members:

  .. autoclasstoc:: marimo._plugins.ui._impl.input.form
```
