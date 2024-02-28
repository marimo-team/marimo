# Tree

```{eval-rst}
.. marimo-embed::
    @app.cell
    def __():
        mo.tree(
            ["entry", "another entry", {"key": [0, mo.ui.slider(1, 10, value=5), 2]}],
            label="A tree of elements.",
        )
        return
```

```{eval-rst}
.. autofunction:: marimo.tree
```
