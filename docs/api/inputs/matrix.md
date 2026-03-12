# Matrix

/// marimo-embed

```python
@app.cell
def __():
    matrix = mo.ui.matrix(
        [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
        min_value=-5,
        max_value=5,
        step=0.1,
        precision=1,
        label="$I$",
    )
    matrix
    return

@app.cell
def __():
    matrix.value
    return
```

///

`mo.ui.matrix` also supports 1D (vector) input:

/// marimo-embed

```python
@app.cell
def __():
    vector = mo.ui.matrix(
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

::: marimo.ui.matrix
