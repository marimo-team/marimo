# Run Button

```{eval-rst}
.. marimo-embed::
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
        mo.stop(not b.value, "Click `run` to submit the slider's value")

        s.value
        return
```

```{eval-rst}
.. autoclass:: marimo.ui.run_button
  :members:

  .. autoclasstoc:: marimo._plugins.ui._impl.run_button.run_button
```
