# Button

```{admonition} Looking for a submit/run button?
:class: tip

If you're looking for a button to trigger computation on click, consider
using [`mo.ui.run_button`](/api/inputs/run_button.md).
```

```{eval-rst}
.. marimo-embed::
    @app.cell
    def __():
        mo.ui.button(label="Click me")
        return
```

```{eval-rst}
.. autoclass:: marimo.ui.button
  :members:

  .. autoclasstoc:: marimo._plugins.ui._impl.input.button
```
