# Plotting

marimo supports most major plotting libraries, including Matplotlib, Seaborn,
Plotly, and Altair. Just import your plotting library of choice and use it
as you normally would.

For more information about plotting, see the [plotting guide](../guides/working_with_data/plotting.md).

## Reactive charts with Altair

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

### Disabling automatic selection

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

::: marimo.ui.altair_chart

### Performance and Data Transformers

Altair has a concept of [data](https://altair-viz.github.io/user_guide/data_transformers.html) transformers, which can be used to improve performance.

Such examples are:

- pandas Dataframe has to be sanitized and serialized to JSON.
- The rows of a Dataframe might need to be sampled or limited to a maximum number.
- The Dataframe might be written to a `.csv` or `.json` file for performance reasons.

By default, Altair uses the `default` data transformer, which is the slowest in marimo. It is limited to 5000 rows (although we increase this to `20_000` rows as marimo can handle this). This includes the data inside the HTML that is being sent over the network, which can also be limited by marimo's maximum message size.

It is recommended to use the `marimo_csv` data transformer, which is the most performant and can handle the largest datasets: it converts the data to a CSV file which is smaller and can be sent over the network. This can handle up to +400,000 rows with no issues.

When using `mo.ui.altair_chart`, we automatically set the data transformer to `marimo_csv` for you. If you are using Altair directly, you can set the data transformer using the following code:

```python
import altair as alt
alt.data_transformers.enable('marimo_csv')
```

## Reactive plots with Plotly

!!! warning "mo.ui.plotly only supports scatter plots, treemaps charts, and sunbursts charts."
    marimo can render any Plotly plot, but [`mo.ui.plotly`][marimo.ui.plotly] only
    supports reactive selections for scatter plots, treemaps charts, and sunbursts charts. If you require other kinds of
    selection, consider using [`mo.ui.altair_chart`][marimo.ui.altair_chart].

::: marimo.ui.plotly

## Interactive matplotlib

::: marimo.mpl.interactive
    options:
      show_root_heading: true
      show_source: true

## Leafmap support

marimo supports rendering [Leafmap](https://leafmap.org/) maps using the `folium` and `plotly` backends.

## Other plotting libraries

You can use all the popular plotting libraries with marimo. Such as:

- [Matplotlib](https://matplotlib.org/)
- [Plotly](https://plotly.com/)
- [Seaborn](https://seaborn.pydata.org/)
- [Bokeh](https://bokeh.org/)
- [Altair](https://altair-viz.github.io/)
- [HoloViews](http://holoviews.org/)
- [hvPlot](https://hvplot.holoviz.org/)
- [Leafmap](https://leafmap.org/)
- [Pygwalker](https://kanaries.net/pygwalker)
