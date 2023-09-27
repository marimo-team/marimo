# Reactive Charts

<!-- <iframe class="demo" src="https://components.marimo.io/?component=slider" frameborder="no"></iframe> -->

marimo supports reactive charts 📈! Any selection made on the chart will be automatically passed to Python in order to create a filtered dataframe for you. marimo also makes it extremely easy to make charts interactive and selectable.

```{admonition} Requirements
:class: warning
Reactive charts depend on Altair and Pandas. If you don't have them installed, you can install them with:

`pip install altair pandas`
```

To support reactive charts, we lean on [Altair](https://altair-viz.github.io/) and the [Vega-Lite Specification](https://vega.github.io/vega-lite/). By doing so, we also support any other libraries or tools that compile to a **Vega or Vega-Lite specification**.

By wrapping your chart in a `marimo.ui.chart` object, you can make it reactive. This means that any selection made in the chart will be automatically passed to Python and a filtered dataframe will be available from the `.value` attribute of the chart.

```python
import altair as alt
import marimo as mo

# Load some data
cars = alt.load_dataset('cars')

# Create a chart
_c = alt.Chart(cars)
  .mark_point() # Mark type
  .encode(
    x='Horsepower', # Encoding along the x-axis
    y='Miles_per_Gallon', # Encoding along the y-axis
    color='Origin', # Category encoding by color
)

# Make it reactive
chart = mo.ui.chart(_c)

# --- new cell --- #

# Display the chart and its data filtered by the selection
mo.vstack([chart, chart.value.head()])
```

## Learning Altair and Vega-Lite

If you're new to **Altair** or **Vega-Lite**, we highly recommend exploring the [Altair documentation](https://altair-viz.github.io/) and [Vega-Lite documentation](https://vega.github.io/vega-lite/). **Altair** simplifies the process of creating **Vega-Lite** charts in Python and is the tool we utilize in many of our examples. **Vega-Lite** an exceptional tool for creating interactive charts and serves as the backbone for marimo's reactive charting capabilities.
// OR
If you're new to Vega-Lite, we highly recommend exploring the [Vega-Lite documentation](https://vega.github.io/vega-lite/). Vega-Lite is an exceptional tool for creating interactive charts and serves as the backbone for marimo's reactive charting capabilities. Additionally, we suggest familiarizing yourself with [Altair](https://altair-viz.github.io/), a Python library specifically designed for generating Vega-Lite charts. **Altair** simplifies the process of creating Vega-Lite charts in Python and is the tool we utilize in many of our examples.

Our choice to use the Vega-Lite specification was driven by its robust data model, which is particularly well-suited for data analysis. The specification is grounded in the following key concepts:

- **Data Source**: This is the information that will be visualized in the chart. It can be provided in various formats such as a dataframe, a list of dictionaries, or a URL pointing to the data source.
- **Mark Type**: This refers to the visual representation used for each data point on the chart. The options include 'bar', 'dot', 'circle', 'area', and 'line'. Each mark type offers a different way to visualize and interpret the data.
- **Encoding**: This is the process of mapping various aspects or dimensions of the data to visual characteristics of the marks. Encodings can be of different types:
  - **Positional Encodings**: These are encodings like 'x' and 'y' that determine the position of the marks in the chart.
  - **Categorical Encodings**: These are encodings like 'color' and 'shape' that categorize data points. They are typically represented in a legend for easy reference.
- **Transformations**: These are operations that can be applied to the data before it is visualized, for example, filtering and aggregation. These transformations allow for more complex and nuanced visualizations.

marimo will add the interactivity automatically, based on the mark used and the encodings. For example, if you use a `mark_point` and an `x` encoding, marimo will automatically add a brush selection to the chart. If you add a `color` encoding, marimo will add a legend and a click selection.

marimo seamlessly integrates interactivity into your charts, the specifics of which are determined by the chosen mark and encodings. For instance, if you opt for a `mark_point` with an `x` encoding, marimo will add a brush selection into your chart. Similarly, with the addition of a `color` encoding, marimo will include a legend with a click selection.

For a comprehensive understanding of the fundamental aspects of the data model, we recommend the [Basic Statistical Visualization](https://altair-viz.github.io/getting_started/starting.html) tutorial from the Altair documentation.

## Automatic Selections

By default `marimo.ui.chart` will make the chart and legend selectable. Depending on the mark type, the chart will either have a `point` or `interval` (brush) selection. When using non-positional encodings (color, size, etc), `marimo.ui.chart` will also make the legend selectable.

This is all configurable through `selection_*` params in `marimo.ui.chart`. See the API docs below for more details.

```{admonition} Note
You may still add your own selection parameters via Altair or Vega-Lite. This is still supported and marimo will not override your selections.
```

```{eval-rst}
.. autoclass:: marimo.ui.chart
  :members:

  .. autoclasstoc:: marimo._plugins.ui._impl.chart.chart
```
