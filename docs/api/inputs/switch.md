# Switch

```{eval-rst}
.. marimo-embed::
    @app.cell
    def __():
        switch = mo.ui.switch(label="do not disturb")
        return

    @app.cell
    def __():
        mo.hstack([switch, mo.md(f"Has value: {switch.value}")])
        return
```

```{eval-rst}
.. autoclass:: marimo.ui.switch
  :members:

  .. autoclasstoc:: marimo._plugins.ui._impl.switch.switch
```
