# Examples

This page includes dozens of bite-sized how-to examples to help you get started
with marimo. Be sure to also read the [quickstart](../getting_started/index.md) and
the [user guide](../guides/index.md), especially the guide on [how marimo runs
cells](../guides/reactivity.md).

!!! Tip "Get inspired at our gallery!"

    For inspirational examples, including embedding-driven
    data labelers, Stanford-scientist authored tutorials, and more,
    check out our [public gallery](https://marimo.io/gallery).


## Running cells

<div class="grid cards" markdown>

-  ⚡️ [**Basic execution**](running_cells/basics.md)

-  🐞 [**Getting around multiple definition errors**](running_cells/multiple_definitions.md)

-  🛑 [**Stop cells from running**](running_cells/stop.md)

-  🖱️ [**Run cells on button click**](running_cells/run_button.md)

-  🕓 [**Refresh on a timer**](running_cells/refresh.md)

-  ⏳ [**Run async functions**](running_cells/async_await.md)

-  💾 [**Caching computations in memory**](running_cells/memory_cache.md)

-  💾 [**Cache computations to persistent storage**](running_cells/persistent_cache.md)

-  🐞 [**Using the debugger**](running_cells/debugging.md)

-  🐍 [**Run notebooks as scripts**](../guides/scripts.md)

</div>

## Visual Outputs

<div class="grid cards" markdown>

-   📤 [**Cell outputs**](outputs/basic_output.md)

-   ✍️  [**Basic markdown**](outputs/basic_markdown.md)

-   💬 [**Console outputs**](outputs/console_outputs.md)

-   📋 [**Capturing console output**](outputs/capture_console_outputs.md)

-   📈 [**Showing plots**](outputs/plots.md)

-   🎥 [**Showing videos and other media**](../api/media/index.md)

-   🎛️ [**Conditionally showing outputs**](outputs/conditional_output.md)

-   🧩 [**Showing multiple outputs in one cell**](outputs/multiple_outputs.md)

</div>

### Writing markdown

<div class="grid cards examples-grid" markdown>

-   ⚡️ [**Python values in markdown**](markdown/dynamic_markdown.md)

    ---

    <a href="markdown/dynamic_markdown"><img src="/_static/example-thumbs/dynamic_markdown.png" /></a>

-   🪄 [**Mermaid diagrams**](markdown/mermaid.md)

    ---

    <a href="markdown/mermaid"><img src="/_static/example-thumbs/mermaid.png" /></a>

-   🚨 [**Admonitions**](markdown/admonitions.md)

    ---

    <a href="markdown/admonitions"><img src="/_static/example-thumbs/admonitions.png" /></a>

-   📂 [**Collapsible details**](markdown/details.md)

    ---

    <a href="markdown/details"><img src="/_static/example-thumbs/details.png" /></a>

-   😀 [**Emoji**](markdown/emoji.md)

</div>

## Working with data

### Dataframes

marimo is designed for working with dataframes. Here are a few examples; see
the [dataframes guide](../guides/working_with_data/dataframes.md) for details.

<div class="grid cards" markdown>

-   🧮 [**Interactive dataframe viewer**](outputs/dataframes.md)

    ---

    <a href="outputs/dataframes"><img src="/_static/example-thumbs/dataframes.png" /></a>

-   🔍 [**Select dataframe rows**](../api/inputs/table.md)

    ---

    <a href="../api/inputs/table"><img src="/_static/example-thumbs/tables.png" /></a>

-   ✏️  [**Editable dataframe**](../api/inputs/data_editor.md)

    ---

    <a href="../api/inputs/data_editor"><img src="/_static/example-thumbs/editable_dataframes.png" /></a>

-   🛠️ [**Interactive dataframe transformer**](../api/inputs/dataframe.md)

    ---

    <a href="../api/inputs/dataframe"><img src="/_static/example-thumbs/dataframe_transformer.png" /></a>

</div>

### SQL

Here are some basic examples, see the [SQL
guide](../guides/working_with_data/sql.md) for more details.

<div class="grid cards examples-grid" markdown>

-   🦆 [**Query dataframes with DuckDB SQL**](../guides/working_with_data/sql.md#example)

-   🛢️ [**SQLite, Postgres, and other engines**](../guides/working_with_data/sql.md#connecting-to-a-custom-database)

</div>

### Plots

See the [plotting guide](../guides/working_with_data/plotting.md) for a full
overview.

<div class="grid cards examples-grid" markdown>

-   📊 [**Selecting data with Altair**](../api/plotting.md#reactive-charts-with-altair)

    ---

    <a href="../api/plotting#reactive-charts-with-altair"><img src="/_static/example-thumbs/altair.png" /></a>

-   📉 [**Selecting data with Plotly**](../guides/working_with_data/plotting.md#plotly)

    ---

    <a href="../guides/working_with_data/plotting#plotly"><img src="/_static/example-thumbs/plotly.png" /></a>

-   🔭 [**Showing matplotlib plots**](outputs/plots.md)

</div>

### Progress bars and status elements

<div class="grid cards examples-grid" markdown>

-   📶 [**Progress bar**](outputs/progress_bar.md)

    ---

    <a href="outputs/progress_bar"><img src="/_static/example-thumbs/progress_bar.png" /></a>

-   🌀 [**Loading spinner**](outputs/spinner.md)

    ---

    <a href="outputs/spinner"><img src="/_static/example-thumbs/spinner.png" /></a>

</div>


### Layouts

<div class="grid cards examples-grid" markdown>

-   📐 [**Horizontal and vertical stacking**](outputs/stacks.md)

    ---

    <a href="outputs/stacks"><img src="/_static/example-thumbs/stacks.png" /></a>

-   📁 [**Accordion toggle**](../api/layouts/accordion.md)

    ---

    <a href="../api/layouts/accordion"><img src="/_static/example-thumbs/accordion.png" /></a>

-   🗂️ [**Tabs**](../api/inputs/tabs.md)

    ---

    <a href="../api/inputs/tabs"><img src="/_static/example-thumbs/tabs.png" /></a>

</div>

## Input elements

### Basic input elements

marimo has a large library of interactive UI elements, which you can use
without callbacks — just make sure to assign elements to global variables. See
the [API reference](../api/inputs/index.md) for a full list, and the [interactivity
guide](../guides/interactivity.md) for rules governing how UI elements work.

<div class="grid cards examples-grid" markdown>

-   🎚️ [**Slider**](../api/inputs/slider.md)

    ---

    <a href="../api/inputs/slider"><img src="/_static/example-thumbs/slider.png" /></a>

-   🧾 [**Dropdown**](../api/inputs/dropdown.md)

    ---

    <a href="../api/inputs/dropdown"><img src="/_static/example-thumbs/dropdown.png" /></a>

-   👆 [**Multi-select**](../api/inputs/multiselect.md)

    ---

    <a href="../api/inputs/multiselect"><img src="/_static/example-thumbs/multiselect.png" /></a>

-   🔘 [**Radio buttons**](../api/inputs/radio.md)

    ---

    <a href="../api/inputs/radio"><img src="/_static/example-thumbs/radio.png" /></a>

-   ☑️ [**Checkbox**](../api/inputs/checkbox.md)

    ---

    <a href="../api/inputs/checkbox"><img src="/_static/example-thumbs/checkbox.png" /></a>

-   📅 [**Date**](../api/inputs/dates.md)

    ---

    <a href="../api/inputs/dates"><img src="/_static/example-thumbs/date.png" /></a>

-   📁 [**File**](../api/inputs/file.md)

    ---

    <a href="../api/inputs/file"><img src="/_static/example-thumbs/file_upload.png" /></a>

-   🔤 [**Text input**](../api/inputs/text.md)

    ---

    <a href="../api/inputs/text"><img src="/_static/example-thumbs/text.png" /></a>

-   📝 [**Text area**](../api/inputs/text_area.md)

    ---

    <a href="../api/inputs/text_area"><img src="/_static/example-thumbs/text_area.png" /></a>

-   🧑‍💻 [**Code editor**](../api/inputs/code_editor.md)

    ---

    <a href="../api/inputs/code_editor"><img src="/_static/example-thumbs/code_editor.png" /></a>

-   🔍 [**Table**](../api/inputs/table.md)

    ---

    <a href="../api/inputs/table"><img src="/_static/example-thumbs/tables.png" /></a>

-   🎙️ [**Microphone**](../api/inputs/microphone.md)

    ---

    <a href="../api/inputs/microphone"><img src="/_static/example-thumbs/microphone.png" /></a>

-   💬 [**Chat**](../api/inputs/chat.md)

    ---

    <a href="../api/inputs/chat"><img src="/_static/example-thumbs/chat.png" /></a>

-   🔢 [**Matrix**](../api/inputs/matrix.md)

    ---

    <a href="../api/inputs/matrix"><img src="/_static/example-thumbs/matrix.png" /></a>

</div>

### Composite input elements

Composite input elements let you create a single UI element from multiple
other UI elements.

<div class="grid cards examples-grid" markdown>

-   🧾 [**Form**](../api/inputs/form.md)

    ---

    <a href="../api/inputs/form"><img src="/_static/example-thumbs/form.png" /></a>

-   🎒 [**Array**](../api/inputs/array.md)

    ---

    <a href="../api/inputs/array"><img src="/_static/example-thumbs/array.png" /></a>

-   📖 [**Dictionary**](../api/inputs/dictionary.md)

    ---

    <a href="../api/inputs/dictionary"><img src="/_static/example-thumbs/dictionary.png" /></a>

</div>
