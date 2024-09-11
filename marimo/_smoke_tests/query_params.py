# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
# ]
# ///
# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.8.14"
app = marimo.App()


@app.cell
def __(mo):
    query_params = mo.query_params()
    return query_params,


@app.cell
def __(mo, query_params):
    # In another cell
    search = mo.ui.text(
        value=query_params["search"] or "",
        on_change=lambda v: query_params.set("search", v),
    )
    search
    return search,


@app.cell
def __(mo):
    toggle = mo.ui.switch(label="Toggle me")
    toggle
    return toggle,


@app.cell
def __(query_params, toggle):
    # change the value of a query param, and watch the next cell run automatically
    query_params["has_run"] = toggle.value
    return


@app.cell
def __(mo):
    new_value = mo.ui.text(label="Text to add")
    return new_value,


@app.cell
def __(mo, new_value, query_params):
    append_button = mo.ui.button(
        label="Add to query param",
        on_click=lambda _: query_params.append("list", new_value.value),
    )
    replace_button = mo.ui.button(
        label="Replace in query param",
        on_click=lambda _: query_params.set("list", new_value.value),
    )
    mo.hstack([new_value, append_button, replace_button])
    return append_button, replace_button


@app.cell
def __(mo, query_params):
    items = [
        {"key": key, "value": str(value)}
        for key, value in query_params.to_dict().items()
    ]
    mo.ui.table(items, selection=None, label="Query params")
    return items,


@app.cell
def __(mo):
    mo.md("""You can also initialized with query params. Open this URL [/?foo=1&bar=2&bar=3&baz=4](/?foo=1&bar=2&bar=3&baz=4) and restart the kernel""")
    return


@app.cell
def __():
    import marimo as mo
    import random
    return mo, random


if __name__ == "__main__":
    app.run()
