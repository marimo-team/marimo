import marimo

__generated_with = "0.16.0"
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
        # Add header info for column headers (shown via info icon + title)
        header_info={
            "first_name": "Employee's first name",
            "last_name": "Employee's last name",
        },
    )
    table
    return (table,)


@app.cell
def _(table):
    table.value
    return


if __name__ == "__main__":
    app.run()
