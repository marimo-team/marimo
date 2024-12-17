# Control flow

Use `mo.stop` to halt execution of a cell, and optionally output an object.
This function is useful for validating user input.

```{eval-rst}
.. autofunction:: marimo.stop
```

```{eval-rst}
.. autoclass:: marimo.MarimoStopError
```

Use `mo.ui.refresh` to trigger other cells to run periodically, on a configurable
interval (or on click).

```{eval-rst}
.. autoclass:: marimo.ui.refresh
  :members:
  :noindex:

  .. autoclasstoc:: marimo._plugins.ui._impl.refresh.refresh
```
