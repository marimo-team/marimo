# Range Slider

```{eval-rst}
.. marimo-embed::
    @app.cell
    def __():
        range_slider = mo.ui.range_slider(start=1, stop=10, step=2, value=[2, 6], full_width=True)
        return

    @app.cell
    def __():
        mo.hstack([range_slider, mo.md(f"Has value: {range_slider.value}")])
        return
```

```{eval-rst}
.. autoclass:: marimo.ui.range_slider
  :members:

  .. autoclasstoc:: marimo._plugins.ui._impl.input.range_slider
```
