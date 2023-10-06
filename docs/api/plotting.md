# Plotting

marimo supports most major plotting libraries, including Matplotlib, Seaborn,
Plotly, and Altair. Just import your plotting library of choice and use it
as you normally would.

```{admonition} Reactive charts: mo.ui.chart!
:class: important

marimo supports reactive charts! Select and filter with your
mouse, and marimo _automatically makes the selected data available in Python
as a Pandas dataframe_!
```


## Reactive charts! ⚡

<!-- <iframe class="demo" src="https://components.marimo.io/?component=chart" frameborder="no"></iframe> -->

_Reactive charts are just one way that marimo **makes your data tangible**_.

marimo has built-in support for reactive charts with
[mo.ui.chart](#`marimo.ui.chart`). Selections on the frontend are automatically
made available as Pandas dataframes in Python.

```{admonition} Requirements
:class: warning
Reactive charts depend on Altair and Pandas. Install them with `pip install altair pandas`
```

To support reactive charts, we build on [Altair](https://altair-viz.github.io/)
and [Vega-Lite](https://vega.github.io/vega-lite/).

Wrap an Altair chart with [marimo.ui.chart](#marimo.ui.chart) to make it
**reactive**: data you select in the frontend is automatically made available
as a filtered dataframe via the chart's `value` attribute (`chart.value`).

```python
import marimo as mo
import altair as alt

# Load some data
cars = alt.load_dataset('cars')

# Create an Altair chart
chart = alt.Chart(cars)
  .mark_point() # Mark type
  .encode(
    x='Horsepower', # Encoding along the x-axis
    y='Miles_per_Gallon', # Encoding along the y-axis
    color='Origin', # Category encoding by color
)

# Make it reactive ⚡
chart = mo.ui.chart(chart)
```

```python
# In a new cell, display the chart and its data filtered by the selection
mo.vstack([chart, chart.value.head()])
```



```{eval-rst}
.. autofunction:: marimo.ui.chart
```

## Using matplotlib
**Tip: outputting matplotlib plots.**
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

```{eval-rst}
.. autofunction:: marimo.mpl.interactive
```
