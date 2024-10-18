import marimo

__generated_with = "0.9.10"
app = marimo.App(width="full")


@app.cell
def __():
    import marimo as mo
    import duckdb
    return duckdb, mo


@app.cell
def __(duckdb):
    duckdb.sql(
        "ATTACH 'md:_share/sample_data/23b0d623-1361-421d-ae77-62d701d471e6' AS sample_data"
    )
    return (sample_data,)


@app.cell
def __(mo):
    mo.md(r"""## Reactive SQL""")
    return


@app.cell
def __(mo):
    last_x_months = mo.ui.slider(24, 30, label="Last x months")
    last_x_months
    return (last_x_months,)


@app.cell
def __(last_x_months, mo):
    recent_hacker_news = mo.sql(
        f"""
        FROM sample_data.hn.hacker_news 
        WHERE timestamp >= (CURRENT_DATE - INTERVAL {last_x_months.value} month)
        AND type = 'story'
        """
    )
    return (recent_hacker_news,)


@app.cell
def __(mo, recent_hacker_news):
    aggregations = mo.sql(
        f"""
        SELECT 
          COUNT(*) AS total_posts, AVG(score) AS avg_score,
          MAX(score) AS max_score, MIN(score) AS min_score,
        FROM recent_hacker_news WHERE score IS NOT NULL;
        """
    )
    return (aggregations,)


@app.cell
def __(mo):
    mo.md(r"""## Mix and match Python""")
    return


@app.cell
def __(mo, sample_data, service_requests):
    agency_tickets = mo.sql(
        f"""
        SELECT 
          agency_name,
          COUNT(*) AS num_requests,
          CAST(SUM(CASE WHEN status = 'Closed' THEN 1 ELSE 0 END) AS INT64) AS closed_count,
          CAST(SUM(CASE WHEN status = 'Open' THEN 1 ELSE 0 END) AS INT64) AS open_count
        FROM sample_data.nyc.service_requests
        GROUP BY agency_name ORDER BY closed_count DESC LIMIT 20
        """
    )
    return (agency_tickets,)


@app.cell
def __(agency_tickets):
    import altair as alt

    scale = alt.Scale(type="sqrt")
    base = (
        alt.Chart(agency_tickets)
        .encode(y="agency_name", x=alt.X("num_requests", scale=scale))
        .properties(width="container")
    )
    chart_closed = base.mark_bar(color="#FFC080").encode(
        x=alt.X("closed_count", scale=scale)
    )
    chart_open = base.mark_bar(color="#8BC34A").encode(
        x=alt.X("open_count", scale=scale)
    )
    chart_closed + chart_open
    return alt, base, chart_closed, chart_open, scale


if __name__ == "__main__":
    app.run()
