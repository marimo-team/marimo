import marimo

__generated_with = "0.15.5"
app = marimo.App()


@app.cell
def _(mo):
    mo.md(r"""[Debounce mo.ui.text and mo.ui.text_area #2218](https://github.com/marimo-team/marimo/issues/2218)""")
    return


@app.cell
def _(debounce, debounce_options, mo):
    name_input = mo.ui.text(
        label="Enter your name for the greeting of a lifetime:", debounce=debounce
    )
    mo.vstack([debounce_options, name_input, name_input])
    return (name_input,)


@app.cell
def _(name_input):
    if len(name_input.value) > 0:
        print(f"Hello {name_input.value}!")
    return


@app.cell
def _(debounce, debounce_options, mo):
    story_input = mo.ui.text_area(
        label="Now tell me a story from your childhood:", debounce=debounce
    )
    mo.vstack([debounce_options, mo.hstack([story_input, story_input])])
    return (story_input,)


@app.cell
def _(story_input):
    if (len(story_input.value) > 0):
        print(story_input.value)
    return


@app.cell
def _(mo):
    debounce_options = mo.ui.dropdown(
        label="Choose debounce option",
        options=["True", "500", "1000", "False"],
        value="True",
    )
    return (debounce_options,)


@app.cell
def _(debounce_options):
    debounce = debounce_options.value
    debounce = (
        int(debounce) if debounce != "True" and debounce != "False" else debounce
    )
    debounce = debounce == "True" if isinstance(debounce, str) else debounce
    return (debounce,)


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()
