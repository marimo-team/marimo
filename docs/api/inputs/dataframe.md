# Dataframe

The dataframe UI element outputs a visual editor to apply "transforms" to a dataframe, such as filtering rows, applying group-bys and aggregations, and more. The transformed dataframe is shown below the transform editor. The UI output also includes the generated Python used to generate the resulting dataframe, which you can copy paste into a cell. You can programmatically access the resulting dataframe by accessing the element's `.value` attribute.

!!! note "Pandas or Polars Required"

    In order to use the dataframe UI element, you must have the `pandas` or `polars` package installed.
    You can install it with `pip install pandas` or `pip install polars`.

Supported transforms are:

- Filter Rows
- Rename Column
- Column Conversion
- Sort Column
- Group By
- Aggregate

/// marimo-embed
    size: large
    app_width: full


```python
    @app.cell
    def __():
        import pandas as pd
        import pyodide
        csv = pyodide.http.open_url("https://raw.githubusercontent.com/mwaskom/seaborn-data/master/iris.csv")
        df = pd.read_csv(csv)
        mo.ui.dataframe(df)
        return
```

///

::: marimo.ui.dataframe
