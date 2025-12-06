# Stat

/// marimo-embed

```python
@app.cell
def _():
    active_users = mo.stat(
        value="1.2M",
        label="Active Users",
        caption="12k from last month",
        direction="increase"
    )

    revenue = mo.stat(
        value="$4.5M",
        label="Revenue",
        caption="8k from last quarter",
        direction="increase"
    )

    conversion = mo.stat(
        value="3.8",
        label="Conversion Rate",
        caption="0.5 from last week",
        direction="decrease",
    )

    mo.hstack([active_users, revenue, conversion], justify="center", gap="2rem")
    return
```

```python
def _():
    import altair as alt
    import polars as pl

    alt.renderers.set_embed_options(actions=False)

    df = pl.DataFrame(
        {
            "revenue": [30, 20, 70, 45],
            "dates": ["01/01/2024", "01/03/2024", "01/06/2024", "01/09/2024"],
        }
    )

    chart = (
        alt.Chart(df)
        .mark_line(interpolate="monotone")
        .encode(
            x=alt.X("dates", axis=None),
            y=alt.Y("revenue", axis=None),
            tooltip=["dates", "revenue"],
        )
        .properties(height=40, width=60, background="transparent")
        .configure_view(strokeWidth=0)
    )

    mo.stat(
        value=df["revenue"][-1],
        label="Revenue",
        caption="QoQ Growth",
        direction="increase",
        bordered=True,
        slot=chart,
    )
    return
```

///

::: marimo.stat
