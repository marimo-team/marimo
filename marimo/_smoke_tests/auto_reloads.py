import marimo

__generated_with = "0.16.3"
app = marimo.App(width="medium")


@app.cell
def _(mo):
    search = mo.ui.text(
        placeholder="type here",
        debounce=300,  # Debounce to avoid too many API calls
    )
    return (search,)


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _(mo, search):
    search_term = search.value.strip()

    search_results = []

    # Only search if we have at least 2 characters
    if len(search_term) < 2:
        print(f"too short. {search_term}")
    else:
        search_results = {search_term: "value1"}


    # Create dropdown from API results
    if search_results:
        dropdown = mo.ui.dropdown(
            options=search_results,
            searchable=True,
            full_width=True,
        )
    else:
        dropdown = mo.md("Type at least 2 characters to search")
    return (dropdown,)


@app.cell
def _(dropdown, mo, search):
    single_drop_down = mo.vstack([search, dropdown])

    mo.ui.tabs({"Single": single_drop_down})
    return


if __name__ == "__main__":
    app.run()
