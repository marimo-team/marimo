# File

/// marimo-embed

```python
@app.cell
def __():
    file_button = mo.ui.file(kind="button")
    file_area = mo.ui.file(kind="area")
    return file_area, file_button
```

```python
@app.cell
def _(file_area, file_button, mo):
    mo.vstack([file_button, file_area])
    return
```

```python
@app.cell
def _(file_area, file_button, mo):
    # Access uploaded files
    mo.vstack([
        mo.md(f"Button upload: {file_button.name() if file_button.value else 'No file'}"),
        mo.md(f"Area upload: {file_area.name() if file_area.value else 'No file'}")
    ])
    return
```

///

::: marimo.ui.file
