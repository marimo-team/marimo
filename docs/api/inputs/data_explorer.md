# Data Explorer

The data explorer UI element outputs a visual editor explore your data via plotting and intelligent recommendations. You can incrementally build your "main" plot by adding different encodings: x-axis, y-axis, color, size, and shape. As you build your plot, the UI element will suggest further plots by intelligently "exploding" an additional encoding derived from your base plot.

```{admonition} Pandas Required
:class: note

In order to use the dataframe UI element, you must have the `pandas` package installed.
You can install it with `pip install pandas`.
```

<!-- <iframe class="demo large" src="https://components.marimo.io/?component=data_explorer" frameborder="no"></iframe> -->

```{eval-rst}
.. autoclass:: marimo.ui.data_explorer
  :members:

  .. autoclasstoc:: marimo._plugins.ui._impl.data_explorer.data_explorer
```
