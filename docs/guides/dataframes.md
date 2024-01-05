# Dataframes

Dataframes are the most common way to display data and interact with data
in Python. marimo makes it easy to interact with dataframes with visualizations
and interactive UI elements.

## Usage

marimo integrates with [Pandas](https://pandas.pydata.org/) dataframes natively without any
additional configuration.

### Creating dataframes

To get started, import Pandas and create a dataframe:

```python
import pandas as pd
pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
```

### Displaying dataframes

You can display dataframes directly in the output area of a cell, by including them
in th last expression of the cell.

<div align="center">
<figure>
<img src="/_static/docs-dataframe-output.png"/>
<figcaption>Display a dataframe in the output area of a cell</figcaption>
</figure>
</div>

You can also display dataframes in rich tables or charts using the [`mo.ui.table`](/api/inputs/table/)
or [`mo.ui.altair_chart`](/api/plotting/) elements. Both of these elements will allow you to pass a Pandas
dataframe directly without any transformation.

<div align="center">
<figure>
<img src="/_static/docs-dataframe-visualizations.png"/>
<figcaption>Display a dataframe in a rich table or chart</figcaption>
</figure>
</div>

### Interacting with dataframes

Additionally, when interacting with marimo elements that accept dataframes, the selection of the element value will be a Pandas dataframe.

```python
# Cell 1 - display a dataframe
df = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
table = mo.ui.table(df, selection="multi")
table

# Cell 2 - display the selection
table.value
```

### Transforming dataframes

Dataframes can be transformed via code and parameterized with other marimo elements, or you can use the [`mo.ui.dataframe`](/api/inputs/dataframe/) element to create a visual form that will allow you to interactively transform the dataframe.

**1. In code with other elements**

```python
# Cell 1 - create a dataframe
df = pd.DataFrame({"person": ["Alice", "Bob", "Charlie"], "age": [20, 30, 40]})

# Cell 2 - create a filter
age_filter = mo.ui.slider(start=0, stop=100, value=50, label="Max age")
age_filter

# Cell 3 - display the transformed dataframe
filtered_df = df[df["age"] < age_filter.value]
mo.ui.table(filtered_df)
```

**2. Using the `mo.ui.dataframe` element**

```python
# Cell 1 - create a dataframe
df = pd.DataFrame({"person": ["Alice", "Bob", "Charlie"], "age": [20, 30, 40]})
transformed_df = mo.ui.dataframe(df)
transformed_df
```

<div align="center">
<figure>
<img src="/_static/docs-dataframe-transform.png"/>
<figcaption>Transform a dataframe with a visual form using the <code>mo.ui.dataframe</code></figcaption>
</figure>
</div>

The `mo.ui.dataframe` element will allow you to interactively transform the dataframe. You can add columns, remove columns, rename columns, filter rows, sort, sample, and more.
The resulting dataframe will be available as the `value` attribute of the element and you can copy and paste the code to recreate the transformation in another cell.

<div align="center">
<figure>
<img src="/_static/docs-dataframe-transform-code.png"/>
<figcaption>Copy the code of the transformation</figcaption>
</figure>
</div>

## Polars support

marimo also supports [Polars](https://pola.rs/) dataframes. Polars can be used directly in [`mo.ui.table`](/api/inputs/table/). You will need to install the `polars` library to use Polars dataframes.

```python
# Cell 1 - create a dataframe
import marimo as mo
import polars as pl
import altair as alt

df = pl.read_csv(
    "https://gist.githubusercontent.com/ritchie46/cac6b337ea52281aa23c049250a4ff03/raw/89a957ff3919d90e6ef2d34235e6bf22304f3366/pokemon.csv"
)

# Cell 2 - visualize in a table
mo.ui.table(df)

# Cell 3 - visualize in a chart
mo.ui.altair_chart(
  alt.Chart(df.to_pandas())
    .mark_circle()
    .encode(
        x="Attack",
        y="Defense",
        size="Total",
        color="Type 1",
        tooltip=["Name", "Total", "Type 1", "Type 2"],
    )
)
```

### Example

Check out an full example [here](https://github.com/marimo-team/marimo/blob/main/examples/third_party/polars.py)

Or run it yourself:

```bash
marimo edit https://raw.githubusercontent.com/marimo-team/marimo/main/examples/third_party/polars.py
```
