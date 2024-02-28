# Slider

```{eval-rst}
.. marimo-embed::
    @app.cell
    def __():
        slider = mo.ui.slider(start=1, stop=20, label="Slider", value=3)
        return

    @app.cell
    def __():
        mo.hstack([slider, mo.md(f"Has value: {slider.value}")])
        return
```

```{eval-rst}
.. autoclass:: marimo.ui.slider
  :members:

  .. autoclasstoc:: marimo._plugins.ui._impl.input.slider
```
