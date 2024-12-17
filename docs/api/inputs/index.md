# Inputs

marimo comes packaged with interactive UI elements that you can use to build
powerful notebooks and apps. These elements are available in `marimo.ui`.

| Element | Description |
|---------|-------------|
| [`marimo.ui.array`](array.md) | Create array inputs |
| [`marimo.ui.batch`](batch.md) | Batch operations |
| [`marimo.ui.button`](button.md) | Create buttons |
| [`marimo.ui.chat`](chat.md) | Create chat interfaces |
| [`marimo.ui.checkbox`](checkbox.md) | Create checkboxes |
| [`marimo.ui.code_editor`](code_editor.md) | Create code editors |
| [`marimo.ui.dataframe`](dataframe.md) | Interactive dataframes |
| [`marimo.ui.data_explorer`](data_explorer.md) | Explore data |
| [`marimo.ui.date`](dates.md) | Date picker |
| [`marimo.ui.datetime`](dates.md) | Date and time picker |
| [`marimo.ui.date_range`](dates.md) | Date range picker |
| [`marimo.ui.dictionary`](dictionary.md) | Dictionary inputs |
| [`marimo.ui.dropdown`](dropdown.md) | Create dropdowns |
| [`marimo.ui.file`](file.md) | File uploads |
| [`marimo.ui.file_browser`](file_browser.md) | Browse files |
| [`marimo.ui.form`](form.md) | Create forms |
| [`marimo.ui.microphone`](microphone.md) | Record audio |
| [`marimo.ui.multiselect`](multiselect.md) | Multiple selection |
| [`marimo.ui.number`](number.md) | Number inputs |
| [`marimo.ui.radio`](radio.md) | Radio buttons |
| [`marimo.ui.range_slider`](range_slider.md) | Range sliders |
| [`marimo.ui.refresh`](refresh.md) | Refresh buttons |
| [`marimo.ui.run_button`](run_button.md) | Run buttons |
| [`marimo.ui.slider`](slider.md) | Create sliders |
| [`marimo.ui.switch`](switch.md) | Toggle switches |
| [`marimo.ui.tabs`](tabs.md) | Tabbed interfaces |
| [`marimo.ui.table`](table.md) | Interactive tables |
| [`marimo.ui.text`](text.md) | Text inputs |
| [`marimo.ui.text_area`](text_area.md) | Multiline text inputs |

To use a UI element, assign it to a global variable and output it in a cell.
When you interact with the frontend element, the Python object's `value`
attribute is automatically updated, and all cells referencing that object
automatically run with the element's latest value.

## Integrations

| Integration | Description |
|-------------|-------------|
| [`marimo.ui.altair_chart`](altair_chart.md) | Interactive Altair charts |
| [`marimo.ui.plotly`](plotly.md) | Interactive Plotly charts |
| [`marimo.mpl.interactive`](mpl.md) | Interactive Matplotlib plots |
| [`marimo.ui.anywidget`](anywidget.md) | Custom widgets |
