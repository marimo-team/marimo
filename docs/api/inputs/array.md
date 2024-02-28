# Array

```{eval-rst}
.. marimo-embed::
    @app.cell
    def __():
        wish = mo.ui.text(placeholder="Wish")
        wishes = mo.ui.array([wish] * 3, label="Three wishes")
        return

    @app.cell
    def __():
        mo.hstack([wishes, wishes.value], justify="space-between")
        return
```

```{eval-rst}
.. autoclass:: marimo.ui.array
  :members:

  .. autoclasstoc:: marimo._plugins.ui._impl.array.array
```
