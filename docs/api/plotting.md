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
