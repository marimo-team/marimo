# Plotting

marimo supports most major plotting libraries, including Matplotlib, Seaborn,
Plotly, Altair, and HoloViews. Just import your plotting library of choice and
use it as you normally would.

For Altair and Plotly plots, marimo does something special: use
[`mo.ui.altair_chart`][marimo.ui.altair_chart] or
[`mo.ui.plotly`][marimo.ui.plotly] to connect frontend
selections to Python!

!!! important "Reactive plots!"

    marimo supports reactive plots via
    [`mo.ui.altair_chart`][marimo.ui.altair_chart] and
    [`mo.ui.plotly`][marimo.ui.plotly]! Select and
    filter with your mouse, and marimo _automatically makes the selected data
    available in Python as a Pandas dataframe_!

## Reactive plots! ⚡

!!! warning "Requirements"

    Reactive plots currently require Altair or Plotly. Install with `pip install
    altair` or `pip install plotly`, depending on which library you are using.
    Selections in plotly are limited to scatter plots, treemaps charts, and sunbursts charts, while Altair supports
    a larger class of plots for selections.

### Altair

/// marimo-embed
    size: large

```python
@app.cell
async def __():
    import pandas as pd
    import pyodide
    import micropip
    import json
    await micropip.install('altair')
    import altair as alt
    return

@app.cell
def __():
    cars = pd.DataFrame(json.loads(
      pyodide.http.open_url('https://vega.github.io/vega-datasets/data/cars.json').read()
    ))

    chart = mo.ui.altair_chart(alt.Chart(cars).mark_point().encode(
        x='Horsepower',
        y='Miles_per_Gallon',
        color='Origin'
    ))
    return

@app.cell
def __():
    mo.vstack([chart, mo.ui.table(chart.value)])
    return
```

///

Use [`mo.ui.altair_chart`][marimo.ui.altair_chart] to easily
create interactive, selectable plots: _selections you make on the frontend are
automatically made available as Pandas dataframes in Python._

<div align="center">
<figure>
<video autoplay muted loop playsinline width="600px" align="center">
    <source src="/_static/docs-intro.mp4" type="video/mp4">
    <source src="/_static/docs-intro.webm" type="video/webm">
</video>
</figure>
</div>

Wrap an Altair chart in [`mo.ui.altair_chart`][marimo.ui.altair_chart]
to make it **reactive**: select data on the frontend, access it via the chart's
`value` attribute (`chart.value`).

#### Disabling automatic selection

marimo automatically adds a default selection based on the mark type, however, you may want to customize the selection behavior of your Altair chart. You can do this by setting `chart_selection` and `legend_selection` to `False`, and using `.add_params` directly on your Altair chart.

```python
# Create an interval selection
brush = alt.selection_interval(encodings=["x"])

_chart = (
    alt.Chart(traces, height=150)
    .mark_line()
    .encode(x="index:Q", y="value:Q", color="traces:N")
    .add_params(brush) # add the selection to the chart
)

chart = mo.ui.altair_chart(
    _chart,
    # disable automatic selection
    chart_selection=False,
    legend_selection=False
)
chart # You can now access chart.value to get the selected data
```

_Reactive plots are just one way that marimo **makes your data tangible**._

#### Example

```python
import marimo as mo
import altair as alt
import vega_datasets

# Load some data
cars = vega_datasets.data.cars()

# Create an Altair chart
chart = alt.Chart(cars).mark_point().encode(
    x='Horsepower', # Encoding along the x-axis
    y='Miles_per_Gallon', # Encoding along the y-axis
    color='Origin', # Category encoding by color
)

# Make it reactive ⚡
chart = mo.ui.altair_chart(chart)
```

```python
# In a new cell, display the chart and its data filtered by the selection
mo.vstack([chart, chart.value.head()])
```

#### Learning Altair

If you're new to **Altair**, we highly recommend exploring the
[Altair documentation](https://altair-viz.github.io/). Altair provides
a declarative, concise, and simple way to create highly interactive and
sophisticated plots.

Altair is based on [Vega-Lite](https://vega.github.io/vega-lite/), an
exceptional tool for creating interactive charts that serves as the backbone
for marimo's reactive charting capabilities.

##### Concepts

!!! warning "Learn by doing? Skip this section!"
    This section summarizes the main concepts used by Altair (and Vega-Lite).
    Feel free to skip this section and return later.

Our choice to use the Vega-Lite specification was driven by its robust data
model, which is well-suited for data analysis. Some key concepts are summarized
below. (For a more detailed explanation, with examples, we recommend the
[Basic Statistical Visualization](https://altair-viz.github.io/getting_started/starting.html)
tutorial from Altair.)

- **Data Source**: This is the information that will be visualized in the
  chart. It can be provided in various formats such as a dataframe, a list of
  dictionaries, or a URL pointing to the data source.
- **Mark Type**: This refers to the visual representation used for each data
  point on the chart. The options include 'bar', 'dot', 'circle', 'area', and
  'line'. Each mark type offers a different way to visualize and interpret the
  data.
- **Encoding**: This is the process of mapping various aspects or dimensions of
  the data to visual characteristics of the marks. Encodings can be of
  different types:
  - **Positional Encodings**: These are encodings like 'x' and 'y' that
    determine the position of the marks in the chart.
  - **Categorical Encodings**: These are encodings like 'color' and 'shape' that
    categorize data points. They are typically represented in a legend for easy
    reference.
- **Transformations**: These are operations that can be applied to the data
  before it is visualized, for example, filtering and aggregation. These
  transformations allow for more complex and nuanced visualizations.

**Automatically interactive.**
marimo adds interactivity automatically, based on the mark used and the
encodings. For example, if you use a `mark_point` and an `x` encoding, marimo
will automatically add a brush selection to the chart. If you add a `color`
encoding, marimo will add a legend and a click selection.

#### Automatic Selections

By default [`mo.ui.altair_chart`][marimo.ui.altair_chart]
will make the chart and legend selectable. Depending on the mark type, the
chart will either have a `point` or `interval` ("brush") selection. When using
non-positional encodings (color, size, etc),
[`mo.ui.altair_chart`][marimo.ui.altair_chart] will also
make the legend selectable.

Selection configurable through `*_selection` params in
[`mo.ui.altair_chart`][marimo.ui.altair_chart]. See the [API
docs][marimo.ui.altair_chart] for details.

!!! note
    You may still add your own selection parameters via Altair or Vega-Lite.
    marimo will not override your selections.

#### Altair transformations

Altair supports a variety of transformations, such as filtering, aggregation, and sorting. These transformations can be used to create more complex and nuanced visualizations. For example, you can use a filter to show only the points that meet a certain condition, or use an aggregation to show the average value of a variable.

In order for marimo's reactive plots to work with transformations, you must install `vegafusion`, as this feature uses `chart.transformed_data` (which requires version 1.4.0 or greater of the `vegafusion` packages).

```bash
# These can be installed with pip using:
pip install "vegafusion[embed]>=1.4.0"
# Or with conda using:
conda install -c conda-forge "vegafusion-python-embed>=1.4.0" "vegafusion>=1.4.0"
```

### Plotly

!!! warning "mo.ui.plotly only supports scatter plots, treemaps charts, and sunbursts charts"

    marimo can render any Plotly plot, but [`mo.ui.plotly`][marimo.ui.plotly] only
    supports reactive selections for scatter plots, treemaps charts, and sunbursts charts. If you require other kinds of
    selection, consider using [`mo.ui.altair_chart`][marimo.ui.altair_chart].

/// marimo-embed
    size: large

```python
@app.cell(hide_code=True)
async def __():
    import micropip
    await micropip.install("pandas")
    await micropip.install("plotly")
    import plotly.express as px
    return micropip, px


@app.cell
def __(px):
    plot = mo.ui.plotly(
      px.scatter(x=[0, 1, 4, 9, 16], y=[0, 1, 2, 3, 4], width=600, height=300)
    )
    plot
    return plot


@app.cell
def __(plot):
    plot.value
    return
```

///

Use [`mo.ui.plotly`][marimo.ui.plotly] to create
selectable Plotly plots whose values are sent back to Python on selection.

## matplotlib

To output a matplotlib plot in a cell's output area, include its `Axes` or
`Figure` object as the last expression in your notebook. For example:

```python
plt.plot([1, 2])
# plt.gca() gets the current `Axes`
plt.gca()
```

or

```python
fig, ax = plt.subplots()

ax.plot([1, 2])
ax
```

If you want to output the plot in the console area, use `plt.show()` or
`fig.show()`.

### Interactive plots

To make matplotlib plots interactive, use
[mo.mpl.interactive][marimo.mpl.interactive].
(Matplotlib plots are not yet reactive.)

## Chart builder

At the bottom left of a table, you can toggle the chart builder. This provides a drag-and-drop interface to create plots.

<div align="center">
<figure>
<video autoplay muted loop playsinline align="center" src="/_static/docs-chart-builder-table.mp4">
</video>
</figure>
</div>

Charts are powered by [Vega-Lite](https://vega.github.io/vega-lite/). To save a chart, click the `+` button in the `Python code` tab to add the code to a new cell.

!!! note

    This feature is in active development. Please report any issues or feedback [here](https://github.com/marimo-team/marimo/issues).