import marimo

__generated_with = "0.8.20"
app = marimo.App(width="columns")


@app.cell(column=0)
def __():
    import marimo as mo
    import altair as alt
    from vega_datasets import data
    return alt, data, mo


@app.cell
def __(dataset, mo, plot, x, y):
    mo.vstack([dataset, x, y, plot])
    return


@app.cell
def __(selected_dataset):
    df = selected_dataset()
    df
    return (df,)


@app.cell(column=1)
def __(plot_type, x, y):
    plot_type().encode(
        x=x.value,
        y=y.value,
    ).interactive()
    return


@app.cell
def __(data, mo):
    dataset = mo.ui.dropdown(
        label="Choose dataset", options=data.list_datasets(), value="iris"
    )
    return (dataset,)


@app.cell
def __(df, mo):
    x = mo.ui.dropdown(
        label="Choose X value", options=df.columns.to_list(), value=df.columns[0]
    )
    y = mo.ui.dropdown(
        label="Choose Y value", options=df.columns.to_list(), value=df.columns[1]
    )
    plot = mo.ui.dropdown(
        label="Choose plot type",
        options=["mark_bar", "mark_circle"],
        value="mark_bar",
    )
    return plot, x, y


@app.cell
def __(data, dataset):
    selected_dataset = getattr(data, dataset.value)
    return (selected_dataset,)


@app.cell
def __(alt, df, plot):
    plot_type = getattr(alt.Chart(df), plot.value)
    return (plot_type,)


if __name__ == "__main__":
    app.run()
