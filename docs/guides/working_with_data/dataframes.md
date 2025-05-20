# Interactive dataframes

**marimo makes you more productive when working with dataframes**.

- [Display dataframes](#displaying-dataframes) in a rich, interactive table and chart views
- [Transform dataframes](#transforming-dataframes) with filters, groupbys,
  aggregations, and more, **no code required**
- [Select data](#selecting-dataframes) from tables or charts and get selections
  back in Python as dataframes

_marimo integrates with [Pandas](https://pandas.pydata.org/) and
[Polars](https://pola.rs) dataframes natively_.

## Displaying dataframes

marimo lets you page through, search, sort, and filter dataframes, making it
extremely easy to get a feel for your data.

<figure>
<video autoplay muted loop playsinline width="100%" height="100%" align="center">
    <source src="/_static/docs-df.mp4" type="video/mp4">
    <source src="/_static/docs-df.webm" type="video/webm">
</video>
<figcaption>marimo brings dataframes to life.</figcaption>
</figure>

Display dataframes by including them in the last expression of the
cell, just like any other object.

/// tab | pandas

```python
import pandas as pd

df = pd.read_json(
    "https://raw.githubusercontent.com/vega/vega-datasets/master/data/cars.json"
)
df
```

///

/// tab | polars

```python
import polars as pl

df = pl.read_json(
    "https://raw.githubusercontent.com/vega/vega-datasets/master/data/cars.json"
)
df
```

///

To opt out of the rich dataframe viewer, use [`mo.plain`][marimo.plain]:

/// tab | pandas

```python
df = pd.read_json(
"https://raw.githubusercontent.com/vega/vega-datasets/master/data/cars.json"
)
mo.plain(df)
```

///

/// tab | polars

```python
df = pl.read_json(
"https://raw.githubusercontent.com/vega/vega-datasets/master/data/cars.json"
)
mo.plain(df)
```

///

## Transforming dataframes

### No-code transformations

Use [`mo.ui.dataframe`][marimo.ui.dataframe] to interactively
transform a dataframe with a GUI, no coding required. When you're done, you
can copy the code that the GUI generated for you and paste it into your
notebook.

<div align="center">
<figure>
<video autoplay muted loop playsinline width="100%" height="100%" align="center" src="/_static/docs-dataframe-transform.webm">
</video>
<figcaption>Build transformations using a GUI</figcaption>
</figure>
</div>

/// tab | pandas

```python
# Cell 1
import marimo as mo
import pandas as pd

df = pd.DataFrame({"person": ["Alice", "Bob", "Charlie"], "age": [20, 30, 40]})
transformed_df = mo.ui.dataframe(df)
transformed_df
```

```python
# Cell 2
# transformed_df.value holds the transformed dataframe
transformed_df.value
```

///

/// tab | polars

```python
# Cell 1
import marimo as mo
import polars as pl

df = pl.DataFrame({"person": ["Alice", "Bob", "Charlie"], "age": [20, 30, 40]})
transformed_df = mo.ui.dataframe(df)
transformed_df
```

```python
# Cell 2
# transformed_df.value holds the transformed dataframe
transformed_df.value
```

///

<div align="center">
<figure>
<img src="/_static/docs-dataframe-transform-code.png"/>
<figcaption>Copy the code of the transformation</figcaption>
</figure>
</div>

### Custom filters

Create custom filters with marimo UI elements, like sliders and dropdowns.

/// tab | pandas

```python
# Cell 1 - create a dataframe
df = pd.DataFrame({"person": ["Alice", "Bob", "Charlie"], "age": [20, 30, 40]})
```

```python
# Cell 2 - create a filter
age_filter = mo.ui.slider(start=0, stop=100, value=50, label="Max age")
age_filter
```

```python
# Cell 3 - display the transformed dataframe
filtered_df = df[df["age"] < age_filter.value]
mo.ui.table(filtered_df)
```

///

/// tab | polars

```python
import marimo as mo
import polars as pl

df = pl.DataFrame({
    "name": ["Alice", "Bob", "Charlie", "David"],
    "age": [25, 30, 35, 40],
    "city": ["New York", "London", "Paris", "Tokyo"]
})

age_filter = mo.ui.slider.from_series(df["age"], label="Max age")
city_filter = mo.ui.dropdown.from_series(df["city"], label="City")

mo.hstack([age_filter, city_filter])
```

```python
# Cell 2
filtered_df = df.filter((pl.col("age") <= age_filter.value) & (pl.col("city") == city_filter.value))
mo.ui.table(filtered_df)
```

///

## Select dataframe rows {#selecting-dataframes}

Display dataframes as interactive, [selectable charts](plotting.md) using
[`mo.ui.altair_chart`][marimo.ui.altair_chart] or
[`mo.ui.plotly`][marimo.ui.plotly], or as a row-selectable table with
[`mo.ui.table`][marimo.ui.table]. Select points in the chart, or select a table
row, and your selection is _automatically sent to Python as a subset of the original
dataframe_.

<div align="center">
<figure>
<video autoplay muted loop playsinline width="100%" height="100%" align="center" src="/_static/docs-dataframe-table.webm">
</video>
<figcaption>Select rows in a table, get them back as a dataframe</figcaption>
</figure>
</div>

/// tab | pandas

```python
# Cell 1 - display a dataframe
import marimo as mo
import pandas as pd

df = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
table = mo.ui.table(df, selection="multi")
table
```

```python
# Cell 2 - display the selection
table.value
```

///

/// tab | polars

```python
# Cell 1 - display a dataframe
import marimo as mo
import polars as pl

df = pl.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
table = mo.ui.table(df, selection="multi")
table
```

```python
# Cell 2 - display the selection
table.value
```

///

## Row viewer panel

To inspect individual rows, you can toggle the Row viewer panel located at the bottom left of a table. While open, click on any row to view. 

For convenience, you can pin the panel to the side of your editor or toggle the focused cell feature, which ensures the value of the currently focused cell is displayed in the panel.

<div align="center">
<figure>
<img src="/_static/docs-row-viewer-panel.gif" width="100%" height="100%" alt="Row viewer panel demonstration (click the bottom left of the table to toggle)">
<figcaption>Open the row viewer panel to display data vertically</figcaption>
</figure>
</div>

## Example notebook

For a comprehensive example of using Polars with marimo, check out our [Polars example notebook](https://github.com/marimo-team/marimo/blob/main/examples/third_party/polars/polars_example.py).

Run it with:

```bash
marimo edit https://raw.githubusercontent.com/marimo-team/marimo/main/examples/third_party/polars/polars_example.py
```
