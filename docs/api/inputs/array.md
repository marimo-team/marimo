# Array

/// marimo-embed

```python
@app.cell
def __():
    wish = mo.ui.text(placeholder="Wish")
    wishes = mo.ui.array([wish] * 3, label="Three wishes")
    return

@app.cell
def __():
    mo.hstack([wishes, wishes.value], justify="space-between")
    return
```

///

::: marimo.ui.array
