# Inputs

marimo comes packaged with interactive UI elements that you can use to build
powerful notebooks and apps. These elements are available in `marimo.ui`.

| Element | Description |
|---------|-------------|
| [`marimo.ui.array`][marimo.ui.array] | Create array inputs |
| [`marimo.ui.batch`][marimo.ui.batch] | Batch operations |
| [`marimo.ui.button`][marimo.ui.button] | Create buttons |
| [`marimo.ui.chat`][marimo.ui.chat] | Create chat interfaces |
| [`marimo.ui.checkbox`][marimo.ui.checkbox] | Create checkboxes |
| [`marimo.ui.code_editor`][marimo.ui.code_editor] | Create code editors |
| [`marimo.ui.dataframe`][marimo.ui.dataframe] | Interactive dataframes |
| [`marimo.ui.data_explorer`][marimo.ui.data_explorer] | Explore data |
| [`marimo.ui.date`][marimo.ui.date] | Date picker |
| [`marimo.ui.datetime`][marimo.ui.datetime] | Date and time picker |
| [`marimo.ui.date_range`][marimo.ui.date_range] | Date range picker |
| [`marimo.ui.dictionary`][marimo.ui.dictionary] | Dictionary inputs |
| [`marimo.ui.dropdown`][marimo.ui.dropdown] | Create dropdowns |
| [`marimo.ui.file`][marimo.ui.file] | File uploads |
| [`marimo.ui.file_browser`][marimo.ui.file_browser] | Browse files |
| [`marimo.ui.form`][marimo.ui.form] | Create forms |
| [`marimo.ui.microphone`][marimo.ui.microphone] | Record audio |
| [`marimo.ui.multiselect`][marimo.ui.multiselect] | Multiple selection |
| [`marimo.ui.number`][marimo.ui.number] | Number inputs |
| [`marimo.ui.radio`][marimo.ui.radio] | Radio buttons |
| [`marimo.ui.range_slider`][marimo.ui.range_slider] | Range sliders |
| [`marimo.ui.refresh`][marimo.ui.refresh] | Refresh buttons |
| [`marimo.ui.run_button`][marimo.ui.run_button] | Run buttons |
| [`marimo.ui.slider`][marimo.ui.slider] | Create sliders |
| [`marimo.ui.switch`][marimo.ui.switch] | Toggle switches |
| [`marimo.ui.tabs`][marimo.ui.tabs] | Tabbed interfaces |
| [`marimo.ui.table`][marimo.ui.table] | Interactive tables |
| [`marimo.ui.text`][marimo.ui.text] | Text inputs |
| [`marimo.ui.text_area`][marimo.ui.text_area] | Multiline text inputs |

To use a UI element, assign it to a global variable and output it in a cell.
When you interact with the frontend element, the Python object's `value`
attribute is automatically updated, and all cells referencing that object
automatically run with the element's latest value.

## Integrations

| Integration | Description |
|-------------|-------------|
| [`marimo.ui.altair_chart`][marimo.ui.altair_chart] | Interactive Altair charts |
| [`marimo.ui.plotly`][marimo.ui.plotly] | Interactive Plotly charts |
| [`marimo.mpl.interactive`][marimo.mpl.interactive] | Interactive Matplotlib plots |
| [`marimo.ui.anywidget`][marimo.ui.anywidget] | Custom widgets |
