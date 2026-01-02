# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.18.2"
app = marimo.App()


@app.cell
def _():
    import marimo as mo
    import polars as pl
    import altair as alt
    return alt, mo, pl


@app.cell
def _(mo):
    _stats = [
        mo.stat("$100", label="Revenue", caption="+ 10%", direction="increase"),
        mo.stat(
            "$20",
            label="Marketing spend",
            caption="+ 10%",
            direction="increase",
            target_direction="decrease",
        ),
        mo.stat("$80", label="Profit", caption="- 10%", direction="decrease"),
        mo.stat(
            "2%",
            label="Churn",
            caption="- 2%",
            direction="decrease",
            target_direction="decrease",
        ),
    ]
    mo.hstack(_stats)
    return


@app.cell
def _(mo):
    _stats = [
        mo.stat(
            "$100",
            label="Revenue",
            caption="+ 10%",
            direction="increase",
            bordered=True,
        ),
        mo.stat(
            "$20",
            label="Marketing spend",
            caption="+ 10%",
            direction="increase",
            bordered=True,
            target_direction="decrease",
        ),
        mo.stat(
            "$80",
            label="Profit",
            caption="- 10%",
            direction="decrease",
            bordered=True,
        ),
        mo.stat(
            "2%",
            label="Churn",
            caption="- 2%",
            direction="decrease",
            bordered=True,
            target_direction="decrease",
        ),
    ]
    mo.hstack(_stats, widths="equal", gap=1)
    return


@app.cell(hide_code=True)
def _(alt, mo, pl):
    findata = pl.DataFrame(
        {
            "revenue": [30, 20, 70, 45, 68, 34, 87, 100],
            "dates": [
                "01/01/2024",
                "01/03/2024",
                "01/06/2024",
                "01/09/2024",
                "01/12/2024",
                "01/15/2024",
                "01/18/2024",
                "01/21/2024",
            ],
        }
    )

    alt.renderers.set_embed_options(actions=False)


    def create_chart(mark: str) -> alt.Chart:
        chart = alt.Chart(findata)
        if mark == "line":
            chart = chart.mark_line(interpolate="monotone")
        else:
            chart = chart.mark_bar()
        chart = (
            chart.encode(
                x=alt.X("dates", axis=None),
                y=alt.Y("revenue", axis=None),
                tooltip=["dates", "revenue"],
            )
            .properties(height=40, width=60, background="transparent")
            .configure_view(strokeWidth=0)
        )
        return chart


    hello_world = mo.Html("<h2><i>Hello, World</i></h2>")

    _stats = [
        mo.stat(
            "$100",
            label="Revenue",
            caption="+ 10%",
            direction="increase",
            bordered=True,
            slot=create_chart("line"),
        ),
        mo.stat(
            "$20",
            label="Marketing spend",
            caption="+ 10%",
            direction="increase",
            target_direction="decrease",
            slot=create_chart("bar"),
        ),
        mo.stat(
            "$80",
            label="Profit",
            caption="- 10%",
            direction="decrease",
            bordered=True,
            slot="🚀🧑‍🚀💰",
        ),
    ]

    _rich = [
        mo.stat(
            "$20",
            label="Marketing spend",
            caption="+ 10%",
            direction="increase",
            target_direction="decrease",
            slot=hello_world,
        ),
        mo.stat(
            "2%",
            label="Churn",
            caption="- 2%",
            direction="decrease",
            bordered=True,
            target_direction="decrease",
            slot=_stats[0],
        ),
    ]


    _first = mo.hstack(_stats, widths="equal", gap=1)
    _second = mo.hstack(_rich, widths="equal", gap=1)

    mo.vstack([_first, _second])
    return


if __name__ == "__main__":
    app.run()
