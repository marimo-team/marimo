# Data Explorer

The data explorer UI element outputs a visual editor explore your data via plotting and intelligent recommendations. You can incrementally build your "main" plot by adding different encodings: x-axis, y-axis, color, size, and shape. As you build your plot, the UI element will suggest further plots by intelligently "exploding" an additional encoding derived from your base plot.

!!! note "Pandas Required"

    In order to use the dataframe UI element, you must have the `pandas` package installed.
    You can install it with `pip install pandas`.

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
    mo.ui.data_explorer(df)
    return
```

///

::: marimo.ui.data_explorer
