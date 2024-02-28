# Inputs

```{eval-rst}
.. toctree::
  :maxdepth: 1
  :hidden:

  array
  batch
  button
  checkbox
  code_editor
  dataframe
  data_explorer
  date
  dictionary
  dropdown
  file
  form
  microphone
  multiselect
  number
  radio
  refresh
  slider
  switch
  table
  tabs
  text
  text_area
```

marimo comes packaged with interactive UI elements that you can use to build
powerful notebooks and apps. These elements are available in `marimo.ui`.

```{eval-rst}
.. autosummary::
  :nosignatures:

  marimo.ui.array
  marimo.ui.batch
  marimo.ui.button
  marimo.ui.checkbox
  marimo.ui.code_editor
  marimo.ui.dataframe
  marimo.ui.data_explorer
  marimo.ui.date
  marimo.ui.dictionary
  marimo.ui.dropdown
  marimo.ui.file
  marimo.ui.form
  marimo.ui.microphone
  marimo.ui.multiselect
  marimo.ui.number
  marimo.ui.radio
  marimo.ui.refresh
  marimo.ui.slider
  marimo.ui.switch
  marimo.ui.tabs
  marimo.ui.table
  marimo.ui.text
  marimo.ui.text_area
```

To use a UI element, assign it to a global variable and output it in a cell.
When you interact with the frontend element, the Python object's `value`
attribute is automatically updated, and all cells referencing that object
automatically run with the element's latest value.

## Integrations

```{eval-rst}
.. autosummary::
  :nosignatures:

  marimo.ui.altair_chart
  marimo.ui.plotly
  marimo.mpl.interactive
```
