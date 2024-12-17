# Code Editor

{{ create_marimo_embed("""

```python
@app.cell
def __():
    mo.ui.code_editor(label="Code Editor", language="python")
    return
```

""") }}

::: marimo.ui.code_editor
