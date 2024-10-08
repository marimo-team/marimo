# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.3.8"
app = marimo.App(width="full")


@app.cell
def __():
    import marimo as mo
    import plotly.express as px
    return mo, px


@app.cell
def __(mo):
    mo.md("# Issue 1064")
    return


@app.cell
def __(px):
    plot1 = px.scatter(x=[0, 1, 4, 9, 16], y=[0, 1, 2, 3, 4])
    plot2 = px.scatter(x=[2, 3, 6, 11, 18], y=[2, 3, 4, 5, 6])
    return plot1, plot2


@app.cell
def __(mo):
    tabs = mo.ui.tabs(
        {
            "💾 Tab 1": "",
            "💾 Tab 2": "",
        }
    )
    return tabs,


@app.cell
def __(mo, plot1, plot2, tabs):
    def render_tab_content():
        if tabs.value == "💾 Tab 1":
            return plot1
        elif tabs.value == "💾 Tab 2":
            return plot2
        else:
            return ""


    mo.vstack([tabs.center(), render_tab_content()])
    return render_tab_content,


if __name__ == "__main__":
    app.run()
