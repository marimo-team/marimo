# Vector

/// marimo-embed

```python
@app.cell
def __():
    vector = mo.ui.vector(
        [1, 0, 0, 0, 0],
        min_value=-5,
        max_value=5,
        step=0.1,
        precision=1,
        label="$\\vec{v}$",
    )
    vector
    return

@app.cell
def __():
    vector.value
    return
```

///

::: marimo.ui.vector
