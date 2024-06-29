# Dataframes

**marimo makes you more productive when working with dataframes**, the most
common Python tool for interacting with data.

- [Display dataframes](#displaying-dataframes) in a rich, interactive table and chart views
- [Select data](#selecting-dataframes) from tables or charts and get selections back as dataframes
- [Transform dataframes](#transforming-dataframes) with filters, groupbys,
  aggregations, and more, **no code required**

_marimo integrates with [Pandas](https://pandas.pydata.org/) and
[Polars](https://pola.rs) dataframes natively. The examples on this page
use Pandas, but Polars works too._

## Displaying dataframes

You can display dataframes directly in the output area of a cell, by including
them in the last expression of the cell:

<div align="center">
<figure>
<img src="/_static/docs-dataframe-output.png"/>
<figcaption>A raw dataframe output</figcaption>
</figure>
</div>

```python
import pandas as pd

df = pd.read_json(
    "https://raw.githubusercontent.com/vega/vega-datasets/master/data/cars.json"
)
df
```

By default the dataframe is displayed using `mo.ui.table`, which provides a
a rich, interactive table view. You can also use `mo.plain` to revert to the
to the default HTML representation.

```python
df = pd.read_json(
    "https://raw.githubusercontent.com/vega/vega-datasets/master/data/cars.json"
)
mo.plain(df)
```

**Rich displays.**
You can display dataframes in rich tables or charts using the
[`mo.ui.table`](/api/inputs/table/) or [`mo.ui.altair_chart`](/api/plotting/)
elements.

<div align="center">
<figure>
<img src="/_static/docs-dataframe-visualizations.png"/>
<figcaption>Rich, interactive displays</figcaption>
</figure>
</div>

```python
import marimo as mo
import altair as alt
import pandas as pd

df = pd.read_json(
    "https://raw.githubusercontent.com/vega/vega-datasets/master/data/cars.json"
)[["Horsepower", "Miles_per_Gallon", "Origin"]]

mo.hstack(
    [
        mo.ui.table(df),
        mo.ui.altair_chart(
            alt.Chart(df)
            .mark_point()
            .encode(x="Horsepower", y="Miles_per_Gallon", color="Origin")
        ),
    ],
    widths="equal",
)
```

## Selecting dataframes

Select data in a [table](#marimo.ui.table) or [Plotly](#marimo.ui.plotly)/[Altair](#marimo.ui.altair_chart) plot,
and your selection is _automatically sent to Python as a Pandas dataframe_.

<div align="center">
<figure>
<img src="/_static/docs-dataframe-table.gif"/>
<figcaption>Select rows in a table, get them back as a dataframe</figcaption>
</figure>
</div>

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

## Transforming dataframes

### No-code transformations

Use [`mo.ui.dataframe`](/api/inputs/dataframe/) to interactively
transform a dataframe with a GUI, no coding required!. When you're done, you
can copy the code that the GUI generated for you and paste it into your
notebook.

<div align="center">
<figure>
<img src="/_static/docs-dataframe-transform.gif"/>
<figcaption>Build transformations using a GUI</figcaption>
</figure>
</div>

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

<div align="center">
<figure>
<img src="/_static/docs-dataframe-transform-code.png"/>
<figcaption>Copy the code of the transformation</figcaption>
</figure>
</div>

### Custom filters

Create custom filters with marimo UI elements, like sliders and dropdowns.

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

## Polars support

marimo also supports [Polars](https://pola.rs/), a
modern, faster alternative to Pandas.

**Example.**

Check out a full example [here](https://github.com/marimo-team/marimo/blob/main/examples/third_party/polars_example.py),
or run it yourself:

```bash
marimo edit https://raw.githubusercontent.com/marimo-team/marimo/main/examples/third_party/polars_example.py
```
