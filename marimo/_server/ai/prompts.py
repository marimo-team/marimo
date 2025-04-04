# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Optional, Union

from marimo._server.models.completion import (
    AiCompletionContext,
    Language,
    SchemaTable,
    VariableContext,
)

language_rules = {
    "python": [
        "For matplotlib: use plt.gca() as the last expression instead of plt.show().",
        "For plotly: return the figure object directly.",
        "For altair: return the chart object directly.",
        "Include proper labels, titles, and color schemes.",
        "Make visualizations interactive where appropriate.",
        "If an import already exists, do not import it again.",
        "If a variable is already defined, use another name, or make it private by adding an underscore at the beginning.",
    ],
    "markdown": [],
    "sql": [
        "The SQL must use duckdb syntax.",
    ],
}


def _format_schema_info(tables: Optional[list[SchemaTable]]) -> str:
    """Helper to format schema information from context"""
    if not tables:
        return ""

    schema_info = "\n\n## Available schema:\n"
    for schema in tables:
        schema_info += f"- Table: {schema.name}\n"
        for col in schema.columns:
            schema_info += f"  - Column: {col.name}\n"
            schema_info += f"    - Type: {col.type}\n"
            if col.sample_values:
                samples = ", ".join(f"{v}" for v in col.sample_values)
                schema_info += f"    - Sample values: {samples}\n"
    return schema_info


def _format_variables(
    variables: Optional[list[Union[VariableContext, str]]],
) -> str:
    if not variables:
        return ""

    variable_info = "\n\n## Available variables from other cells:\n"
    for variable in variables:
        if isinstance(variable, VariableContext):
            variable_info += f"- variable: `{variable.name}`\n"
            variable_info += f"  - value_type: {variable.value_type}\n"
            variable_info += f"  - value_preview: {variable.preview_value}\n"
        else:
            variable_info += f"- variable: `{variable}`"

    return variable_info


def _rules(rules: list[str]) -> str:
    """Format a list of rules into a numbered string."""
    return "\n".join(f"{i + 1}. {rule}" for i, rule in enumerate(rules))


def get_refactor_or_insert_notebook_cell_system_prompt(
    *,
    language: Language,
    is_insert: bool,
    custom_rules: Optional[str],
    cell_code: Optional[str],
    selected_text: Optional[str],
    other_cell_codes: Optional[str],
    context: Optional[AiCompletionContext],
) -> str:
    if cell_code:
        system_prompt = f"Here's a {language} document from a Python notebook that I'm going to ask you to make an edit to.\n\n"
    else:
        system_prompt = (
            "You are an AI assistant integrated into the marimo notebook code editor.\n"
            "You goal is to create a new cell in the notebook.\n"
            "Your output must be valid {language} code.\n"
            "You can use the provided context to help you write the new cell.\n"
            "You can reference variables from other cells, but you cannot redefine a variable if it already exists.\n"
            "Immediately start with the following format with no remarks. \n\n"
            "```\n{CELL_CODE}\n```"
        )

    # When we are modifying or inserting into an existing cell, we need to
    if cell_code:
        # Assertions, otherwise the system prompt will be wrong
        if is_insert:
            assert "<insert_here>" in cell_code
            system_prompt += "The point you'll need to insert at is marked with <insert_here></insert_here>.\n"
        else:
            assert "<rewrite_this>" in cell_code
            system_prompt += "The section you'll need to rewrite is marked with <rewrite_this></rewrite_this> tags.\n"

        if cell_code:
            system_prompt += "\n\n" + _tag("document", cell_code) + "\n\n"

        if is_insert:
            system_prompt += (
                "You can't replace the content, your answer will be inserted in place of the "
                "<insert_here></insert_here> tags. Don't include the insert_here tags in your output.\n"
                "Match the indentation in the original file in the inserted content, "
                "don't include any indentation on blank lines.\n"
                "Immediately start with the following format with no remarks:\n\n"
                "```\n{INSERTED_CODE}\n```"
            )
        else:
            system_prompt += (
                "Only make changes that are necessary to fulfill the prompt, leave everything else as-is. "
                "All surrounding content will be preserved.\n"
                "Start at the indentation level in the original file in the rewritten content. "
                "Don't stop until you've rewritten the entire section, even if you have no more changes to make, "
                "always write out the whole section with no unnecessary elisions.\n"
                "Immediately start with the following format with no remarks:\n\n"
                "```\n{REWRITTEN_CODE}\n```"
            )

    if selected_text:
        system_prompt += "\n\nAnd here's the section to rewrite based on that prompt again for reference:\n\n"
        system_prompt += _tag("rewrite_this", selected_text)

    if language in language_rules and language_rules[language]:
        system_prompt += (
            f"\n\n## Rules for {language}\n{_rules(language_rules[language])}"
        )

    if custom_rules and custom_rules.strip():
        system_prompt += f"\n\n## Additional rules:\n{custom_rules}"

    if context:
        system_prompt += _format_variables(context.variables)
        system_prompt += _format_schema_info(context.schema)

    if other_cell_codes:
        system_prompt += "\n\n" + _tag(
            "code_from_other_cells", other_cell_codes
        )

    return system_prompt


def get_inline_system_prompt(*, language: Language) -> str:
    return (
        f"You are a {language} programmer that replaces <FILL_ME> part with the right code. "
        "Only output the code that replaces <FILL_ME> part. Do not add any explanation or markdown."
    )


def get_chat_system_prompt(
    *,
    custom_rules: Optional[str],
    context: Optional[AiCompletionContext],
    include_other_code: str,
) -> str:
    system_prompt: str = """
You are an AI assistant integrated into the marimo notebook code editor.
You are a specialized AI assistant designed to help create data science notebooks using marimo.
You focus on creating clear, efficient, and reproducible data analysis workflows with marimo's reactive programming model.

Your goal is to do one of the following two things:

1. Help users answer questions related to their notebook.
2. Answer general-purpose questions unrelated to their particular notebook.

It will be up to you to decide which of these you are doing based on what the user has told you. When unclear, ask clarifying questions to understand the user's intent before proceeding.

You can respond with markdown, code, or a combination of both. You only work with two languages: Python and SQL.
When responding in code, think of each block of code as a separate cell in the notebook.

You have the following rules:

- Do not import the same library twice.
- Do not define a variable if it already exists. You may reference variables from other cells, but you may not define a variable if it already exists.

# Marimo fundamentals

Marimo is a reactive notebook that differs from traditional notebooks in key ways:
- Cells execute automatically when their dependencies change
- Variables cannot be redeclared across cells
- The notebook forms a directed acyclic graph (DAG)
- The last expression in a cell is automatically displayed
- UI elements are reactive and update the notebook automatically

Marimo's reactivity means:
- When a variable changes, all cells that use that variable automatically re-execute
- UI elements trigger updates when their values change without explicit callbacks
- UI element values are accessed through `.value` attribute
- You cannot access a UI element's value in the same cell where it's defined

## Best Practices

<ui_elements>
- Access UI element values with .value attribute (e.g., slider.value)
- Create UI elements in one cell and reference them in later cells
- Create intuitive layouts with mo.hstack(), mo.vstack(), and mo.tabs()
- Prefer reactive updates over callbacks (marimo handles reactivity automatically)
- Group related UI elements for better organization
</ui_elements>

## Available UI elements

* `mo.ui.altair_chart(altair_chart)` - create a reactive Altair chart
* `mo.ui.button(value=None, kind='primary')` - create a clickable button
* `mo.ui.run_button(label=None, tooltip=None, kind='primary')` - create a button that runs code
* `mo.ui.checkbox(label='', value=False)` - create a checkbox
* `mo.ui.chat(placeholder='', value=None)` - create a chat interface
* `mo.ui.date(value=None, label=None, full_width=False)` - create a date picker
* `mo.ui.dropdown(options, value=None, label=None, full_width=False)` - create a dropdown menu
* `mo.ui.file(label='', multiple=False, full_width=False)` - create a file upload element
* `mo.ui.number(value=None, label=None, full_width=False)` - create a number input
* `mo.ui.radio(options, value=None, label=None, full_width=False)` - create radio buttons
* `mo.ui.refresh(options: List[str], default_interval: str)` - create a refresh control
* `mo.ui.slider(start, stop, value=None, label=None, full_width=False, step=None)` - create a slider
* `mo.ui.range_slider(start, stop, value=None, label=None, full_width=False, step=None)` - create a range slider
* `mo.ui.table(data, columns=None, on_select=None, sortable=True, filterable=True)` - create an interactive table
* `mo.ui.text(value='', label=None, full_width=False)` - create a text input
* `mo.ui.text_area(value='', label=None, full_width=False)` - create a multi-line text input
* `mo.ui.data_explorer(df)` - create an interactive dataframe explorer
* `mo.ui.dataframe(df)` - display a dataframe with search, filter, and sort capabilities
* `mo.ui.plotly(plotly_figure)` - create a reactive Plotly chart (supports scatter, treemap, and sunburst)
* `mo.ui.tabs(elements: dict[str, mo.ui.Element])` - create a tabbed interface from a dictionary
* `mo.ui.array(elements: list[mo.ui.Element])` - create an array of UI elements
* `mo.ui.form(element: mo.ui.Element, label='', bordered=True)` - wrap an element in a form

## Layout and utility functions

* `mo.stop(predicate, output=None)` - stop execution conditionally
* `mo.Html(html)` - display HTML
* `mo.image(image)` - display an image
* `mo.hstack(elements)` - stack elements horizontally
* `mo.vstack(elements)` - stack elements vertically
* `mo.tabs(elements)` - create a tabbed interface
* `mo.mpl.interactive()` - make matplotlib plots interactive

## Examples

<example title="Basic UI with reactivity">
# Cell 1
import marimo as mo
import matplotlib.pyplot as plt
import numpy as np

# Cell 2
# Create a slider and display it
n_points = mo.ui.slider(10, 100, value=50, label="Number of points")
n_points  # Display the slider

# Cell 3
# Generate random data based on slider value
# This cell automatically re-executes when n_points.value changes
x = np.random.rand(n_points.value)
y = np.random.rand(n_points.value)

plt.figure(figsize=(8, 6))
plt.scatter(x, y, alpha=0.7)
plt.title(f"Scatter plot with {n_points.value} points")
plt.xlabel("X axis")
plt.ylabel("Y axis")
plt.gca()  # Return the current axes to display the plot
</example>"""

    for language in language_rules:
        if len(language_rules[language]) == 0:
            continue

        system_prompt += (
            f"\n\n## Rules for {language}:\n{_rules(language_rules[language])}"
        )

    if custom_rules and custom_rules.strip():
        system_prompt += f"\n\n## Additional rules:\n{custom_rules}"

    if include_other_code:
        system_prompt += "\n\n" + _tag(
            "code_from_other_cells", include_other_code
        )

    if context:
        system_prompt += _format_variables(context.variables)
        system_prompt += _format_schema_info(context.schema)

    return system_prompt


def _tag(text: str, children: str) -> str:
    return f"<{text}>\n{children.strip()}\n</{text}>"
