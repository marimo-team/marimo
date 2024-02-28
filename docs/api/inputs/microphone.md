# Microphone

```{eval-rst}
.. marimo-embed::
    @app.cell
    def __():
        microphone = mo.ui.microphone(label="Drop a beat!")
        return

    @app.cell
    def __():
        mo.hstack([microphone, mo.audio(microphone.value)])
        return
```

```{eval-rst}
.. autoclass:: marimo.ui.microphone
  :members:

  .. autoclasstoc:: marimo._plugins.ui._impl.microphone.microphone
```
