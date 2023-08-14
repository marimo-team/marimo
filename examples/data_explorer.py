import marimo

__generated_with = "0.1.0"
app = marimo.App()


@app.cell
def __(mo):
    mo.md("# Data Explorer")
    return


@app.cell
def __(mo):
    mo.md("This notebook lets you upload a CSV and plot its columns.")
    return


@app.cell
def __(df, mo, uploaded_file):
    callout_kind = (
        "alert"
        if (uploaded_file.name() is None)
        else "neutral"
    )

    mo.md(
        f"""
        {mo.hstack([mo.md("**Upload a CSV.**")], "center")}

        {uploaded_file}

        {mo.as_html(df.head()) if df is not None else ""}
        """
    ).callout(kind=callout_kind)
    return callout_kind,


@app.cell
def __(io, mo, pd, uploaded_file):
    df = None
    columns = None
    plot_type = mo.ui.dropdown(
        ["line", "hist"], value="line", label="Choose a plot type: "
    )

    if uploaded_file.name() is not None:
        df = pd.read_csv(io.StringIO(uploaded_file.contents().decode()))
        columns = mo.ui.dropdown(df.columns[1:], label="Choose a column: ")
    return columns, df, plot_type


@app.cell
def __(columns, mo, plot_type):
    def column_selector():
        if columns is None:
            return None

        return mo.hstack([columns, plot_type], justify="space-around").callout(
            kind="warn" if columns.value is None else "neutral"
        )

    column_selector()
    return column_selector,


@app.cell
def __(columns, df, plot_type, plt):
    def plot_data():
        if df is not None and columns.value is not None:
            data = df[columns.value].to_numpy()
            if plot_type.value == "line":
                plt.plot(data)
            else:
                plt.hist(data)
            plt.title(columns.value)
            return plt.gca()
        else:
            return None


    plot = plot_data()
    plot
    return plot, plot_data


@app.cell
def __(mo):
    uploaded_file = mo.ui.file(filetypes=[".csv"], kind="area")
    return uploaded_file,


@app.cell
def __():
    import marimo as mo

    import io
    import matplotlib.pyplot as plt
    import pandas as pd
    return io, mo, pd, plt


if __name__ == "__main__":
    app.run()
