# Run Button

{{ create_marimo_embed("""

```python
@app.cell
def __():
    b = mo.ui.run_button()
    b
    return

@app.cell
def __():
    s = mo.ui.slider(1, 10)
    s
    return

@app.cell
def __():
    mo.stop(not b.value, \"Click `run` to submit the slider's value\")

    s.value
    return
```

""", size="medium") }}

::: marimo.ui.run_button
