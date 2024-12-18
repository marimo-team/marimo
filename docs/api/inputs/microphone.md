# Microphone

/// marimo-embed

```python
@app.cell
def __():
    microphone = mo.ui.microphone(label="Drop a beat!")
    return

@app.cell
def __():
    mo.hstack([microphone, mo.audio(microphone.value)])
    return
```

///

::: marimo.ui.microphone
