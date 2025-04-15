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

<div class="grid cards" markdown>

-   ⚡️ [**Python values in markdown**](markdown/dynamic_markdown.md)

-   🪄 [**Mermaid diagrams**](markdown/mermaid.md)

-   🚨 [**Admonitions**](markdown/admonitions.md)

-   📂 [**Collapsible details**](markdown/details.md)

-   😀 [**Emoji**](markdown/emoji.md)

</div>

## Working with data

### Dataframes

marimo is designed for working with dataframes. Here are a few examples; see
the [dataframes guide](../guides/working_with_data/dataframes.md) for details.

<div class="grid cards" markdown>

-   🧮 [**Interactive dataframe viewer**](outputs/dataframes.md)

-   🔍 [**Select dataframe rows**](../api/inputs/table.md)

-   ✏️  [**Editable dataframe**](../api/inputs/data_editor.md)

-   🛠️ [**Interactive dataframe transformer**](../api/inputs/dataframe.md)

</div>

### SQL

Here are some basic examples, see the [SQL
guide](../guides/working_with_data/sql.md) for more details.

<div class="grid cards" markdown>

-   🦆 [**Query dataframes with DuckDB SQL**](../guides/working_with_data/sql.md#example)

-   🛢️ [**SQLite, Postgres, and other engines**](../guides/working_with_data/sql.md#connecting-to-a-custom-database)

</div>

### Plots

See the [plotting guide](../guides/working_with_data/plotting.md) for a full
overview.

<div class="grid cards" markdown>

-   📊 [**Selecting data with Altair**](../api/plotting.md#reactive-charts-with-altair)

-   📉 [**Selecting data with Plotly**](../api/plotting.md#reactive-charts-with-plotly)

-   🔭 [**Showing matplotlib plots**](outputs/plots.md)

</div>

### Progress bars and status elements

<div class="grid cards" markdown>

-   📶 [**Progress bar**](outputs/progress_bar.md)

-   🌀 [**Loading spinner**](outputs/spinner.md)

</div>

### Layouts

<div class="grid cards" markdown>

-   📐 [**Horizontal and vertical stacking**](outputs/stacks.md)

-   📁 [**Accordion toggle**](../api/layouts/accordion.md)

-   🗂️ [**Tabs**](../api/inputs/tabs.md)

</div>

## Input elements

### Basic input elements

marimo has a large library of interactive UI elements, which you can use
without callbacks — just make sure to assign elements to global variables. See
the [API reference](../api/inputs/index.md) for a full list, and the [interactivity
guide](../guides/interactivity.md) for rules governing how UI elements work.

<div class="grid cards" markdown>

-   🎚️ [**Slider**](../api/inputs/slider.md)

-   🧾 [**Dropdown**](../api/inputs/dropdown.md)

-   👆 [**Multi-select**](../api/inputs/multiselect.md)

-   🔘 [**Radio buttons**](../api/inputs/radio.md)

-   ☑️ [**Checkbox**](../api/inputs/checkbox.md)

-   📅 [**Date**](../api/inputs/dates.md)

-   📁 [**File**](../api/inputs/file.md)

-   🔤 [**Text input**](../api/inputs/text.md)

-   📝 [**Text area**](../api/inputs/text_area.md)

-   🧑‍💻 [**Code editor**](../api/inputs/code_editor.md)

-   🎙️ [**Microphone**](../api/inputs/microphone.md)

-   💬 [**Chat**](../api/inputs/chat.md)

</div>

### Composite input elements

Composite input elements let you create a single UI element from multiple
other UI elements.

<div class="grid cards" markdown>

-   🧾 [**Form**](../api/inputs/form.md)

-   🎒 [**Array**](../api/inputs/array.md)

-   📖 [**Dictionary**](../api/inputs/dictionary.md)

</div>
