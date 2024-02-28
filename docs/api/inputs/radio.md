# Radio

```{eval-rst}
.. marimo-embed::
    @app.cell
    def __():
        options = ["Apples", "Oranges", "Pears"]
        radio = mo.ui.radio(options=options)
        return

    @app.cell
    def __():
        mo.hstack([radio, mo.md(f"Has value: {radio.value}")])
        return
```

```{eval-rst}
.. autoclass:: marimo.ui.radio
  :members:

  .. autoclasstoc:: marimo._plugins.ui._impl.input.radio
```
