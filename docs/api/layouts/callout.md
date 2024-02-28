# Callout

```{eval-rst}
.. marimo-embed::
    @app.cell
    def __():
        callout_kind = mo.ui.dropdown(
            label="Color",
            options=["neutral", "danger", "warn", "success"],
            value="neutral",
        )
        return

    @app.cell
    def __():
        callout = mo.callout("This is a callout", kind=callout_kind.value)
        return

    @app.cell
    def __():
        mo.vstack([callout_kind, callout], align="stretch", gap=0)
        return
```

```{eval-rst}
.. autofunction:: marimo.callout
```
