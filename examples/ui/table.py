import marimo

__generated_with = "0.19.7"
app = marimo.App()


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    # ui.table accepts a list of rows as dicts, or a dict mapping column names to values,
    # or a dataframe-like object
    table = mo.ui.table(
        [
            {"first_name": "Michael", "last_name": "Scott"},
            {"first_name": "Jim", "last_name": "Halpert"},
            {"first_name": "Pam", "last_name": "Beesly"},
        ],
        # Show full name on hover for each row using column placeholders
        hover_template="{{first_name}} {{last_name}}",
        # Add header tooltip for column headers (shown via info icon + title)
        header_tooltip={
            "first_name": "Employee's first name",
            "last_name": "Employee's last name",
        },
    )
    table
    return (table,)


@app.cell
def _(mo):
    # Per-cell hover: provide a callable for finer control
    def cell_hover(row_id: str, column_name: str, value) -> str:
        return f"{row_id}:{column_name}={value}"

    hover_table = mo.ui.table(
        [{"a": i, "b": i * i} for i in range(8)],
        hover_template=cell_hover,
    )
    hover_table
    return


@app.cell
def _(table):
    table.value
    return


@app.cell
def _(mo):
    # Demonstrate a long table with a sticky header and a custom max height
    long_rows = [{"row": i, "first_name": f"First {i}", "last_name": f"Last {i}"} for i in range(200)]
    long_table = mo.ui.table(
        long_rows,
        pagination=False,
        max_height=300,
    )
    long_table
    return


if __name__ == "__main__":
    app.run()
