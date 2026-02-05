import marimo

__generated_with = "0.19.7"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    # Create a form with multiple elements
    form = (
        mo.md(
            """
            **Your form.**

            {name}

            {date}
            """
        )
        .batch(
            name=mo.ui.text(label="name"),
            date=mo.ui.date(label="date"),
        )
        .form(show_clear_button=True, bordered=False)
    )
    form
    return (form,)


@app.cell
def _(form):
    form.value
    return


if __name__ == "__main__":
    app.run()
