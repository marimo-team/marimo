/* Copyright 2024 Marimo. All rights reserved. */

export function getAgentPrompt(filename: string) {
  return `
  I am currently editing a marimo notebook.
  You can read or write to the notebook at ${filename}

  If you make edits to the notebook, only edit the contents inside the function decorator with @app.cell.
  marimo will automatically handle adding the parameters and return statement of the function. For example,
  for each edit, just return:

  \`\`\`
  @app.cell
  def _():
    <your code here>
    return
  \`\`\`

  ## Marimo fundamentals

  Marimo is a reactive notebook that differs from traditional notebooks in key ways:

  - Cells execute automatically when their dependencies change
  - Variables cannot be redeclared across cells
  - The notebook forms a directed acyclic graph (DAG)
  - The last expression in a cell is automatically displayed
  - UI elements are reactive and update the notebook automatically

  ## Code Requirements

  1. All code must be complete and runnable
  2. Follow consistent coding style throughout
  3. Include descriptive variable names and helpful comments
  4. Import all modules in the first cell, always including \`import marimo as mo\`
  5. Never redeclare variables across cells
  6. Ensure no cycles in notebook dependency graph
  7. The last expression in a cell is automatically displayed, just like in Jupyter notebooks.
  8. Don't include comments in markdown cells
  9. Don't include comments in SQL cells
  10. Never define anything using \`global\`.

  ## Reactivity

  Marimo's reactivity means:

  - When a variable changes, all cells that use that variable automatically re-execute
  - UI elements trigger updates when their values change without explicit callbacks
  - UI element values are accessed through \`.value\` attribute
  - You cannot access a UI element's value in the same cell where it's defined

  ## Best Practices

  <data_handling>
  - Use pandas for data manipulation
  - Implement proper data validation
  - Handle missing values appropriately
  - Use efficient data structures
  - A variable in the last expression of a cell is automatically displayed as a table
  </data_handling>

  <visualization>
  - For matplotlib: use plt.gca() as the last expression instead of plt.show()
  - For plotly: return the figure object directly
  - For altair: return the chart object directly
  - Include proper labels, titles, and color schemes
  - Make visualizations interactive where appropriate
  </visualization>

  <ui_elements>
  - Access UI element values with .value attribute (e.g., slider.value)
  - Create UI elements in one cell and reference them in later cells
  - Create intuitive layouts with mo.hstack(), mo.vstack(), and mo.tabs()
  - Prefer reactive updates over callbacks (marimo handles reactivity automatically)
  - Group related UI elements for better organization
  </ui_elements>

  <sql>
  - When writing duckdb, prefer using marimo's SQL cells, which start with _df = mo.sql(query)
  - See the SQL with duckdb example for an example on how to do this
  - Don't add comments in cells that use mo.sql()
  - Consider using \`vega_datasets\` for common example datasets
  </sql>

  ## Troubleshooting

  Common issues and solutions:
  - Circular dependencies: Reorganize code to remove cycles in the dependency graph
  - UI element value access: Move access to a separate cell from definition
  - Visualization not showing: Ensure the visualization object is the last expression

  ## Available UI elements

  - \`mo.ui.altair_chart(altair_chart)\`
  - \`mo.ui.button(value=None, kind='primary')\`
  - \`mo.ui.run_button(label=None, tooltip=None, kind='primary')\`
  - \`mo.ui.checkbox(label='', value=False)\`
  - \`mo.ui.date(value=None, label=None, full_width=False)\`
  - \`mo.ui.dropdown(options, value=None, label=None, full_width=False)\`
  - \`mo.ui.file(label='', multiple=False, full_width=False)\`
  - \`mo.ui.number(value=None, label=None, full_width=False)\`
  - \`mo.ui.radio(options, value=None, label=None, full_width=False)\`
  - \`mo.ui.refresh(options: List[str], default_interval: str)\`
  - \`mo.ui.slider(start, stop, value=None, label=None, full_width=False, step=None)\`
  - \`mo.ui.range_slider(start, stop, value=None, label=None, full_width=False, step=None)\`
  - \`mo.ui.table(data, columns=None, on_select=None, sortable=True, filterable=True)\`
  - \`mo.ui.text(value='', label=None, full_width=False)\`
  - \`mo.ui.text_area(value='', label=None, full_width=False)\`
  - \`mo.ui.data_explorer(df)\`
  - \`mo.ui.dataframe(df)\`
  - \`mo.ui.plotly(plotly_figure)\`
  - \`mo.ui.tabs(elements: dict[str, mo.ui.Element])\`
  - \`mo.ui.array(elements: list[mo.ui.Element])\`
  - \`mo.ui.form(element: mo.ui.Element, label='', bordered=True)\`

  ## Layout and utility functions

  - \`mo.md(text)\` - display markdown
  - \`mo.stop(predicate, output=None)\` - stop execution conditionally
  - \`mo.output.append(value)\` - append to the output when it is not the last expression
  - \`mo.output.replace(value)\` - replace the output when it is not the last expression
  - \`mo.Html(html)\` - display HTML
  - \`mo.image(image)\` - display an image
  - \`mo.hstack(elements)\` - stack elements horizontally
  - \`mo.vstack(elements)\` - stack elements vertically
  - \`mo.tabs(elements)\` - create a tabbed interface



  ## Examples

  <example title="Markdown ccell">
  ${formatCells([
    `
  mo.md("""
  # Hello world
  This is a _markdown_ **cell**.
  """)
    `,
  ])}
  </example>

  <example title="Basic UI with reactivity">
  ${formatCells([
    `
  import marimo as mo
  import matplotlib.pyplot as plt
  import numpy as np
    `,
    `
  n_points = mo.ui.slider(10, 100, value=50, label="Number of points")
  n_points
    `,
    `
  x = np.random.rand(n_points.value)
  y = np.random.rand(n_points.value)

  plt.figure(figsize=(8, 6))
  plt.scatter(x, y, alpha=0.7)
  plt.title(f"Scatter plot with {n_points.value} points")
  plt.xlabel("X axis")
  plt.ylabel("Y axis")
  plt.gca()
    `,
  ])}
  </example>

  <example title="Data explorer">
  ${formatCells([
    `
  import marimo as mo
  import pandas as pd
  from vega_datasets import data
    `,
    `
  cars_df = data.cars()
  mo.ui.data_explorer(cars_df)
    `,
  ])}
  </example>

  <example title="Multiple UI elements">
  ${formatCells([
    `
  import marimo as mo
  import pandas as pd
  import matplotlib.pyplot as plt
  import seaborn as sns
    `,
    `
  iris = sns.load_dataset('iris')
    `,
    `
  species_selector = mo.ui.dropdown(
      options=["All"] + iris["species"].unique().tolist(),
      value="All",
      label="Species"
  )
  x_feature = mo.ui.dropdown(
      options=iris.select_dtypes('number').columns.tolist(),
      value="sepal_length",
      label="X Feature"
  )
  y_feature = mo.ui.dropdown(
      options=iris.select_dtypes('number').columns.tolist(),
      value="sepal_width",
      label="Y Feature"
  )
  mo.hstack([species_selector, x_feature, y_feature])
    `,
    `
  filtered_data = iris if species_selector.value == "All" else iris[iris["species"] == species_selector.value]

  plt.figure(figsize=(10, 6))
  sns.scatterplot(
      data=filtered_data,
      x=x_feature.value,
      y=y_feature.value,
      hue="species"
  )
  plt.title(f"{y_feature.value} vs {x_feature.value}")
  plt.gca()
    `,
  ])}
  </example>

  <example title="Conditional Outputs">
  ${formatCells([
    `
  mo.stop(not data.value, mo.md("No data to display"))

  if mode.value == "scatter":
    mo.output.replace(render_scatter(data.value))
  else:
    mo.output.replace(render_bar_chart(data.value))
    `,
  ])}
  </example>

  <example title="Interactive chart with Altair">
  ${formatCells([
    `
  import marimo as mo
  import altair as alt
  import pandas as pd
    `,
    `# Load dataset
  cars_df = pd.read_csv('<https://raw.githubusercontent.com/vega/vega-datasets/master/data/cars.json>')
  _chart = alt.Chart(cars_df).mark_point().encode(
      x='Horsepower',
      y='Miles_per_Gallon',
      color='Origin',
  )
  `,
    "chart = mo.ui.altair_chart(_chart)\nchart",
    `
  # Display the selection
  chart.value`,
  ])}
  </example>

  <example title="Run Button Example">
  ${formatCells([
    "import marimo as mo",
    `
  first_button = mo.ui.run_button(label="Option 1")
  second_button = mo.ui.run_button(label="Option 2")
  [first_button, second_button]`,
    `
  if first_button.value:
      print("You chose option 1!")
  elif second_button.value:
      print("You chose option 2!")
  else:
      print("Click a button!")`,
  ])}
  </example>

  <example title="SQL with duckdb">
  ${formatCells([
    "import marimo as mo\nimport pandas as pd",
    `cars_df = pd.read_csv('<https://raw.githubusercontent.com/vega/vega-datasets/master/data/cars.json>')`,
    `_df = mo.sql("SELECT * from cars_df WHERE Miles_per_Gallon > 20")`,
  ])}
  </example>`;
}

function formatCells(cells: string[]) {
  // Option 1:
  // return cells.map((cell) => {
  //   return `# Cell ${cell}`;
  // });

  const indent = "    ";
  const indentCode = (code: string) => {
    return code
      .trim()
      .split("\n")
      .map((line) => indent + line)
      .join("\n");
  };

  // Option 2:
  const formatCell = (cell: string) => {
    return `
  @app.cell
  def __():
  ${indentCode(cell)}
      return
  `;
  };

  return cells.map(formatCell).join("");
}
