# Slider

/// marimo-embed

```python
@app.cell
def __():
    slider = mo.ui.slider(start=1, stop=20, label="Slider", value=3)
    return

@app.cell
def __():
    mo.hstack([slider, mo.md(f"Has value: {slider.value}")])
    return

@app.cell
def __():
    # You can also use steps to create a slider on a custom range
    log_slider = mo.ui.slider(steps=np.logspace(-2, 2, 101), label="Logarithmic Slider", value=1)
    return

@app.cell
def __():
    mo.hstack([log_slider, mo.md(f"Has value: {log_slider.value}")])
    return

@app.cell
def __():
    import numpy as np
    return
```

///

::: marimo.ui.slider
