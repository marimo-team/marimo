# Switch

/// marimo-embed

```python
@app.cell
def __():
    switch = mo.ui.switch(label="do not disturb")
    return

@app.cell
def __():
    mo.hstack([switch, mo.md(f"Has value: {switch.value}")])
    return
```

///

::: marimo.ui.switch
