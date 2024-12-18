# Refresh

/// marimo-embed

```python
@app.cell
def __():
    refresh = mo.ui.refresh(
      label="Refresh",
      options=["1s", "5s", "10s", "30s"]
    )
    return

@app.cell
def __():
    mo.hstack([refresh, refresh.value])
    return
```

///

::: marimo.ui.refresh
