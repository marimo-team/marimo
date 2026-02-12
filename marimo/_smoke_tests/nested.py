# Smoke tests for nested marimo custom elements.
# Verifies that interactive widgets, lazy loading, and layout components
# work correctly when nested inside each other (especially inside shadow DOM).
# Related: https://github.com/marimo-team/marimo/issues/5129

import marimo

__generated_with = "0.19.11"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    # Nested components smoke tests
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Table inside tabs
    """)
    return


@app.cell
def _(mo):
    import pandas as pd

    df = pd.DataFrame({"name": ["Alice", "Bob", "Charlie"], "age": [25, 30, 35]})
    table_in_tabs = mo.ui.tabs(
        {
            "Table": mo.ui.table(df),
            "Plain": mo.md("No table here"),
        }
    )
    table_in_tabs
    return (pd,)


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Table inside accordion
    """)
    return


@app.cell
def _(mo, pd):
    df2 = pd.DataFrame({"x": [1, 2, 3], "y": [4, 5, 6]})
    mo.accordion(
        {
            "Show table": mo.ui.table(df2),
            "Show text": mo.md("Just text"),
        }
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Lazy inside tabs (issue #5129)
    """)
    return


@app.cell
def _(mo):
    call_count_1 = []


    def lazy_fn_1():
        call_count_1.append(1)
        print(f"lazy_fn_1 called (total: {len(call_count_1)}x)")
        return mo.md(f"Loaded! Call count: {len(call_count_1)}")


    lazy_tabs = mo.ui.tabs(
        {
            "Normal": mo.md("This tab is normal"),
            "Lazy": mo.lazy(lazy_fn_1, show_loading_indicator=True),
        }
    )
    lazy_tabs
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Lazy inside accordion
    """)
    return


@app.cell
def _(mo):
    call_count_2 = []


    def lazy_fn_2():
        call_count_2.append(1)
        print(f"lazy_fn_2 called (total: {len(call_count_2)}x)")
        return mo.md(f"Loaded! Call count: {len(call_count_2)}")


    mo.accordion(
        {
            "Click to lazy load": mo.lazy(lazy_fn_2, show_loading_indicator=True),
        }
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Tabs with `lazy=True`
    """)
    return


@app.cell
def _(mo, pd):
    df3 = pd.DataFrame({"a": range(10), "b": range(10, 20)})

    auto_lazy_tabs = mo.ui.tabs(
        {
            "Tab A": mo.md("First tab content"),
            "Tab B": mo.ui.table(df3),
            "Tab C": mo.md("Third tab content"),
        },
        lazy=True,
    )
    auto_lazy_tabs
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Accordion with `lazy=True`
    """)
    return


@app.cell
def _(mo):
    mo.accordion(
        {
            "Section 1": mo.md("Content 1"),
            "Section 2": mo.md("Content 2"),
            "Section 3": mo.md("Content 3"),
        },
        lazy=True,
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Interactive widgets inside tabs
    """)
    return


@app.cell
def _(mo):
    slider = mo.ui.slider(0, 100, value=50, label="Slider in tab")
    checkbox = mo.ui.checkbox(label="Checkbox in tab")
    dropdown = mo.ui.dropdown(
        ["Option A", "Option B", "Option C"], label="Dropdown in tab"
    )
    text_input = mo.ui.text(placeholder="Type here...", label="Text in tab")
    return checkbox, dropdown, slider, text_input


@app.cell
def _(checkbox, dropdown, mo, slider, text_input):
    widget_tabs = mo.ui.tabs(
        {
            "Slider": mo.vstack([slider, mo.md(f"Value: {slider.value}")]),
            "Checkbox": mo.vstack([checkbox, mo.md(f"Checked: {checkbox.value}")]),
            "Dropdown": mo.vstack(
                [dropdown, mo.md(f"Selected: {dropdown.value}")]
            ),
            "Text": mo.vstack([text_input, mo.md(f"Typed: {text_input.value}")]),
        }
    )
    widget_tabs
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Tabs inside tabs
    """)
    return


@app.cell
def _(mo):
    inner_tabs = mo.ui.tabs(
        {
            "Inner A": mo.md("Inner tab A"),
            "Inner B": mo.md("Inner tab B"),
        }
    )
    outer_tabs = mo.ui.tabs(
        {
            "Outer 1": inner_tabs,
            "Outer 2": mo.md("Outer tab 2"),
        }
    )
    outer_tabs
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Accordion inside tabs
    """)
    return


@app.cell
def _(mo):
    mo.ui.tabs(
        {
            "With accordion": mo.accordion(
                {
                    "Section A": mo.md("Accordion content A"),
                    "Section B": mo.md("Accordion content B"),
                }
            ),
            "Plain tab": mo.md("Just a plain tab"),
        }
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Tabs inside accordion
    """)
    return


@app.cell
def _(mo):
    mo.accordion(
        {
            "Open for tabs": mo.ui.tabs(
                {
                    "Tab X": mo.md("Tab X content"),
                    "Tab Y": mo.md("Tab Y content"),
                }
            ),
        }
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Lazy table inside tabs
    """)
    return


@app.cell
def _(mo, pd):
    def lazy_table():
        print("lazy_table called")
        df = pd.DataFrame({"col1": range(5), "col2": range(5, 10)})
        return mo.ui.table(df)


    mo.ui.tabs(
        {
            "Normal": mo.md("Normal content"),
            "Lazy table": mo.lazy(lazy_table, show_loading_indicator=True),
        }
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Deeply nested: lazy inside accordion inside tabs
    """)
    return


@app.cell
def _(mo):
    def deep_lazy_fn():
        print("deep_lazy_fn called")
        return mo.md("Deeply nested lazy content loaded!")


    mo.ui.tabs(
        {
            "Top tab": mo.accordion(
                {
                    "Open for lazy": mo.lazy(
                        deep_lazy_fn, show_loading_indicator=True
                    ),
                }
            ),
            "Other tab": mo.md("Other"),
        }
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## hstack/vstack inside tabs
    """)
    return


@app.cell
def _(mo):
    mo.ui.tabs(
        {
            "Horizontal": mo.hstack(
                [mo.md("**Left**"), mo.md("**Center**"), mo.md("**Right**")],
                justify="space-between",
            ),
            "Vertical": mo.vstack(
                [mo.md("**Top**"), mo.md("**Middle**"), mo.md("**Bottom**")],
                gap=1,
            ),
        }
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Callout inside tabs
    """)
    return


@app.cell
def _(mo):
    mo.ui.tabs(
        {
            "Info": mo.callout(mo.md("This is an info callout"), kind="info"),
            "Warning": mo.callout(mo.md("This is a warning callout"), kind="warn"),
            "Danger": mo.callout(mo.md("This is a danger callout"), kind="danger"),
        }
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Form inside tabs
    """)
    return


@app.cell
def _(mo):
    form = mo.ui.text(placeholder="Enter name").form()
    return (form,)


@app.cell
def _(form, mo):
    mo.ui.tabs(
        {
            "Form tab": form,
            "Result tab": mo.md(f"Submitted: {form.value}"),
        }
    )
    return


if __name__ == "__main__":
    app.run()
