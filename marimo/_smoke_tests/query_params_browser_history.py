import marimo

__generated_with = "0.11.22"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _(mo):
    query_params = mo.query_params()


    def set_tab(tab):
        query_params["tab"] = tab


    def get_tab():
        return query_params.get("tab", "Tab 1")
    return get_tab, query_params, set_tab


@app.cell
def _(mo):
    tabs = {
        "Tab 1": mo.md("Hello World!"),
        "Tab 2": mo.md("Hello World?"),
        "Tab 3": mo.md("Hello? Anyone there?"),
    }
    return (tabs,)


@app.cell
def _(get_tab, mo, set_tab, tabs):
    tab_view = mo.ui.tabs(
        tabs,
        value=get_tab(),
        on_change=lambda tab: set_tab(tab),
    )
    return (tab_view,)


@app.cell
def _(tab_view):
    tab_view
    return


@app.cell
def _(query_params):
    query_params
    return


if __name__ == "__main__":
    app.run()
