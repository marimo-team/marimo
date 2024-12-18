# Range Slider

/// marimo-embed

```python
@app.cell
def __():
    range_slider = mo.ui.range_slider(start=1, stop=10, step=2, value=[2, 6], full_width=True)
    return

@app.cell
def __():
    mo.hstack([range_slider, mo.md(f"Has value: {range_slider.value}")])
    return
```

///

::: marimo.ui.range_slider
