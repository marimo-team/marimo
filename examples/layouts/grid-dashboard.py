# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "altair==5.4.1",
#     "hvplot==0.10.0",
#     "marimo",
#     "matplotlib==3.9.2",
#     "numpy==2.1.1",
#     "openai==1.49.0",
#     "pandas==2.2.3",
#     "panel==1.5.0",
#     "plotly==5.24.1",
# ]
# ///

import marimo

__generated_with = "0.13.10"
app = marimo.App(
    width="medium",
    layout_file="layouts/grid-dashboard.grid.json",
)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""# Gapminder Dashboard""")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        rf"""
    /// TIP 

    "This notebook is best viewed as an app."

    `marimo run {__file__}`

    or hit `Cmd/Ctrl+.` or click the "app view" button in the bottom right.
    ///
    """
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        """
    If you would like to see _how_ this application is made, continue down.

    This application is adapted from <https://examples.holoviz.org/gallery/gapminders/gapminders.html>
    """
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""# Getting the data""")
    return


@app.cell
def _():
    import numpy as np
    import pandas as pd
    import panel as pn
    import marimo as mo

    import altair as alt
    import plotly.graph_objs as go
    import plotly.io as pio
    import matplotlib.pyplot as plt
    import matplotlib as mpl
    import hvplot.pandas  # noqa
    import warnings

    warnings.simplefilter("ignore")
    pn.extension("vega", "plotly", defer_load=True, sizing_mode="stretch_width")
    mpl.use("agg")
    return alt, go, mo, np, pd, pio, plt


@app.cell
def _():
    XLABEL = "GDP per capita (2000 dollars)"
    YLABEL = "Life expectancy (years)"
    YLIM = (20, 90)
    HEIGHT = 500  # pixels
    WIDTH = 500  # pixels
    ACCENT = "#D397F8"
    PERIOD = 1000  # milliseconds
    return HEIGHT, XLABEL, YLABEL, YLIM


@app.cell
def _(pd):
    dataset = pd.read_csv(
        "https://raw.githubusercontent.com/kirenz/datasets/b8f17b8fc4907748b3317554d65ffd780edcc057/gapminder.csv"
    )
    dataset.sample(5)
    return (dataset,)


@app.cell
def _(dataset):
    YEARS = [int(year) for year in dataset.year.unique()]
    str(YEARS)
    return (YEARS,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""# Charting the data""")
    return


@app.cell
def _(dataset, np):
    # Common utility functions


    def get_data(year):
        df = dataset[(dataset.year == year) & (dataset.gdpPercap < 10000)].copy()
        df["size"] = np.sqrt(df["pop"] * 2.666051223553066e-05)
        df["size_hvplot"] = df["size"] * 6
        return df


    def get_title(library, year):
        return f"{library}: Life expectancy vs. GDP, {year}"


    def get_xlim(data):
        return (
            dataset["gdpPercap"].min() - 100,
            dataset[dataset["gdpPercap"] < 10000].max()["gdpPercap"] + 1000,
        )
    return get_data, get_title, get_xlim


@app.cell
def _(XLABEL, YLABEL, YLIM, alt, get_data, get_title, get_xlim, go, pio, plt):
    # Charting functions


    def mpl_view(year=1952, show_legend=True):
        data = get_data(year)
        title = get_title("Matplotlib", year)
        xlim = get_xlim(data)

        plot = plt.figure(figsize=(10, 8), facecolor=(0, 0, 0, 0))
        ax = plot.add_subplot(111)
        ax.set_xscale("log")
        ax.set_title(title)
        ax.set_xlabel(XLABEL)
        ax.set_ylabel(YLABEL)
        ax.set_ylim(YLIM)
        ax.set_xlim(xlim)

        for continent, df in data.groupby("continent"):
            ax.scatter(
                df.gdpPercap,
                y=df.lifeExp,
                s=df["size"] * 5,
                edgecolor="black",
                label=continent,
            )

        if show_legend:
            ax.legend(loc=4)

        plt.close(plot)
        return plot


    pio.templates.default = None


    def plotly_view(year=1952, show_legend=True):
        data = get_data(year)
        title = get_title("Plotly", year)
        xlim = get_xlim(data)
        ylim = YLIM
        traces = []
        for continent, df in data.groupby("continent"):
            marker = dict(
                symbol="circle",
                sizemode="area",
                sizeref=0.1,
                size=df["size"],
                line=dict(width=2),
            )
            traces.append(
                go.Scatter(
                    x=df.gdpPercap,
                    y=df.lifeExp,
                    mode="markers",
                    marker=marker,
                    name=continent,
                    text=df.country,
                )
            )

        axis_opts = dict(
            gridcolor="rgb(255, 255, 255)", zerolinewidth=1, ticklen=5, gridwidth=2
        )
        layout = go.Layout(
            title=title,
            showlegend=show_legend,
            xaxis=dict(title=XLABEL, type="linear", range=xlim, **axis_opts),
            yaxis=dict(title=YLABEL, range=ylim, **axis_opts),
            autosize=True,
            paper_bgcolor="rgba(0,0,0,0)",
        )
        return go.Figure(data=traces, layout=layout)


    def altair_view(
        year=1952, show_legend=True, height="container", width="container"
    ):
        data = get_data(year)
        title = get_title("Altair/ Vega", year)
        xlim = get_xlim(data)
        legend = {} if show_legend else {"legend": None}
        return (
            alt.Chart(data)
            .mark_circle()
            .encode(
                alt.X(
                    "gdpPercap:Q",
                    scale=alt.Scale(type="log", domain=xlim),
                    axis=alt.Axis(title=XLABEL),
                ),
                alt.Y(
                    "lifeExp:Q",
                    scale=alt.Scale(zero=False, domain=YLIM),
                    axis=alt.Axis(title=YLABEL),
                ),
                size=alt.Size("pop:Q", scale=alt.Scale(type="log"), legend=None),
                color=alt.Color(
                    "continent", scale=alt.Scale(scheme="category10"), **legend
                ),
                tooltip=["continent", "country"],
            )
            .configure_axis(grid=False)
            .properties(
                title=title, height=height, width=width, background="rgba(0,0,0,0)"
            )
            .configure_view(fill="white")
            .interactive()
        )


    def hvplot_view(year=1952, show_legend=True):
        data = get_data(year)
        title = get_title("hvPlot/ Bokeh", year)
        xlim = get_xlim(data)

        return data.hvplot.scatter(
            "gdpPercap",
            "lifeExp",
            by="continent",
            s="size_hvplot",
            alpha=0.8,
            logx=True,
            title=title,
            legend="bottom_right",
            hover_cols=["country"],
            ylim=YLIM,
            xlim=xlim,
            ylabel=YLABEL,
            xlabel=XLABEL,
            height=400,
        )
    return altair_view, hvplot_view, mpl_view, plotly_view


@app.cell
def _(HEIGHT, altair_view, hvplot_view, mo, mpl_view, plotly_view):
    mo.ui.tabs(
        {
            "matplotlib": mpl_view(1952, True),
            "plotly": plotly_view(),
            "altair": altair_view(height=HEIGHT - 100),
            "hvplot": hvplot_view(),
        }
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""# Building a dashboard""")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""## Creating widgets""")
    return


@app.cell
def _(YEARS, mo):
    get_year, set_year = mo.state(YEARS[-1])
    return get_year, set_year


@app.cell
def _(YEARS, get_year, mo, set_year):
    year = mo.ui.slider(
        value=get_year(), steps=YEARS, full_width=True, on_change=set_year
    )
    show_legend = mo.ui.checkbox(value=True, label="Show Legend")
    return show_legend, year


@app.cell
def _(mo, show_legend, year):
    mo.vstack(
        [
            mo.md(f"Year: **{year.value}**"),
            year,
            show_legend,
        ]
    )
    return


@app.cell
def _(mo):
    autoplay = mo.ui.refresh(options=["1s", "3s", "5s"], label="Autoplay")
    autoplay
    return (autoplay,)


@app.cell
def _(YEARS, autoplay, set_year):
    autoplay


    def increment(v):
        if v is None:
            return YEARS[-1]
        index = (YEARS.index(v) + 1) % len(YEARS)
        return YEARS[index]


    set_year(increment)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""## Creating the charts, reactive to the widgets""")
    return


@app.cell
def _(mpl_view, show_legend, year):
    mpl_view(year=year.value, show_legend=show_legend.value)
    return


@app.cell
def _(plotly_view, show_legend, year):
    plotly_view(year=year.value, show_legend=show_legend.value)
    return


@app.cell
def _(HEIGHT, altair_view, show_legend, year):
    altair_view(year=year.value, show_legend=show_legend.value, height=HEIGHT - 100)
    return


@app.cell
def _(hvplot_view, show_legend, year):
    hvplot_view(year=year.value, show_legend=show_legend.value)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        """
    ## Add any extra flair

    Next we will toggle to "App view" (hit `Cmd/Ctrl+.` or click the "app view") in order to layout our dashboard with the grid layout editor.
    """
    )
    return


@app.cell
def _(mo):
    mo.image("https://marimo.io/logotype-wide.svg")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        """
    ## 🎓 Info

    Here you can try out four different plotting libraries controlled by a couple of widgets, for Hans Rosling's [gapminder](https://demo.bokeh.org/gapminder) example.

    This application is inspired by [Panel](https://examples.holoviz.org/gallery/gapminders/gapminders.html).
    """
    )
    return


if __name__ == "__main__":
    app.run()
