# Plotting

marimo supports most major plotting libraries, including Matplotlib, Seaborn,
Plotly, and Altair. Just import your plotting library of choice and use it
as you normally would.

For more information about plotting, see the [plotting guide](../guides/plotting.md).

## Reactive charts with Altair

```{eval-rst}
.. marimo-embed::
    :size: large

    @app.cell
    async def __():
        import pandas as pd
        import pyodide
        import micropip
        await micropip.install('altair')
        return

    @app.cell
    def __():
        import altair as alt
        cars = pyodide.http.open_url('https://vega.github.io/vega-datasets/data/cars.json')

        chart = alt.Chart(cars).mark_point().encode(
            x='Horsepower',
            y='Miles_per_Gallon',
            color='Origin'
        )
        return

    @app.cell
    def __():
        mo.vstack([chart, mo.ui.table(chart.value)])
        return
```

```{eval-rst}
.. autofunction:: marimo.ui.altair_chart
```

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

```{eval-rst}
.. autofunction:: marimo.ui.plotly
```

## Interactive matplotlib

```{eval-rst}
.. autofunction:: marimo.mpl.interactive
```

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
