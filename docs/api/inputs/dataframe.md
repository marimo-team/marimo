# Dataframe

The dataframe UI element outputs a visual editor to apply "transforms" to a dataframe, such as filtering rows, applying group-bys and aggregations, and more. The transformed dataframe is shown below the transform editor. The UI output also includes the generated Python used to generate the resulting dataframe, which you can copy paste into a cell. You can programmatically access the resulting dataframe by accessing the element's `.value` attribute.

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

```{eval-rst}
.. marimo-embed::
    :size: large
    :app_width: full

    @app.cell
    def __():
        import pandas as pd
        import pyodide
        csv = pyodide.http.open_url("https://raw.githubusercontent.com/mwaskom/seaborn-data/master/iris.csv")
        df = pd.read_csv(csv)
        mo.ui.dataframe(df)
        return
```

```{eval-rst}
.. autoclass:: marimo.ui.dataframe
  :members:

  .. autoclasstoc:: marimo._plugins.ui._impl.dataframes.dataframe.dataframe
```
