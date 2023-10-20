# Dataframe

The dataframe UI element will output a visual editor to apply "transforms" to a dataframe. The resulting dataframe will be show below the transform editor. The UI output also includes the generated Python used to generate the resulting dataframe. You can programmatically access the resulting dataframe by accessing the element's `.value` attribute.

```{admonition} Pandas Required
:class: note

In order to use the dataframe UI element, you must have the `pandas` package installed.
You can install it with `pip install pandas`.
```

Supported transforms are:

- Filter Rows
- Rename Column
- Column Conversion
- Sort Column
- Group By
- Aggregate

<!-- <iframe class="demo large" src="https://components.marimo.io/?component=dataframe" frameborder="no"></iframe> -->

```{eval-rst}
.. autoclass:: marimo.ui.dataframe
  :members:

  .. autoclasstoc:: marimo._plugins.ui._impl.dataframes.dataframe.dataframe
```
