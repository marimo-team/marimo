# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "altair==5.4.1",
#     "duckdb==1.1.0",
#     "polars==1.18.0",
#     "pyarrow==18.1.0",
#     "marimo",
# ]
# ///

import marimo

__generated_with = "0.17.4"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # MotherDuck 🧡 marimo

    Throughout this notebook, we will explore using [MotherDuck](https://motherduck.com) inside marimo. If you’re new to marimo, check out our [GitHub](https://github.com/marimo-team/marimo) repo: marimo is free and open source.

    _You can expand the code of any cells to see how the output are being created._
    """)
    return


@app.cell(hide_code=True)
def _(md_token, mo):
    callout = mo.md(f"""
    There is no **MotherDuck** token found in your environment. To set one up, go to the [MotherDuck's settings page](https://app.motherduck.com/settings/general), create a token, and copy it below.
    And re-run this notebook:

    ```console
    motherduck_token="YOUR_TOKEN_HERE" marimo edit {__file__}
    ```
    """).callout()

    if md_token is None:
        mo.output.replace(
            mo.accordion({"Tired of logging in to MotherDuck?": callout})
        )
    return


@app.cell(hide_code=True)
def _():
    import os

    md_token = os.environ.get("motherduck_token") or os.environ.get(
        "MOTHERDUCK_TOKEN"
    )
    return (md_token,)


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    Let's attach a remote MotherDuck database using `md:`
    """)
    return


@app.cell
def _():
    import duckdb
    import marimo as mo

    duckdb.sql(
        "ATTACH 'md:_share/sample_data/23b0d623-1361-421d-ae77-62d701d471e6' AS sample_data"
    )
    # or add your own md instance
    # duckdb.sql(f"ATTACH IF NOT EXISTS 'md:sample_data'")
    return duckdb, mo


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    !!! tip "Explore data sources"
        If you open the "Explore data sources" panel on the left side bar (3rd icon), you will see all your tables including any news ones we will create below
    """)
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## Let's make some queries 🦆
    """)
    return


@app.cell
def _(mo):
    most_shared_websites = mo.sql(
        f"""
        -- Most shared websites
        -- This query returns the top domains being shared on Hacker News.

        SELECT
            regexp_extract(url, 'http[s]?://([^/]+)/', 1) AS domain,
            count(*) AS count
        FROM sample_data.hn.hacker_news
        WHERE url IS NOT NULL AND regexp_extract(url, 'http[s]?://([^/]+)/', 1) != ''
        GROUP BY domain
        ORDER BY count DESC
        LIMIT 20;

        -- We've named the result of this dataframe to be `most_shared_websites`. Now we can use this in any downstream Python or SQL code.
        """
    )
    return (most_shared_websites,)


@app.cell
def _(mo):
    most_commented_stories_each_month = mo.sql(
        f"""
        -- Most Commented Stories Each Month
        -- This query calculates the total number of comments for each story and identifies the most commented story of each month.
        WITH ranked_stories AS (
            SELECT
                title,
                'https://news.ycombinator.com/item?id=' || id AS hn_url,
                descendants AS nb_comments,
                YEAR(timestamp) AS year,
                MONTH(timestamp) AS month,
                ROW_NUMBER()
                    OVER (
                        PARTITION BY YEAR(timestamp), MONTH(timestamp) 
                        ORDER BY descendants DESC
                    )
                AS rn
            FROM sample_data.hn.hacker_news
            WHERE type = 'story'
        )

        SELECT
            year,
            month,
            title,
            hn_url,
            nb_comments
        FROM ranked_stories
        WHERE rn = 1
        ORDER BY year, month;

        -- This also creates a table most_commented_stories_each_month
        -- Which can be used in Python to create charts
        """
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Let's make some charts 📈

    Now that we have made some queries and named the results, we can chart those resulting dataframes in Python, using our favorite charting libraries (e.g [altair](https://altair-viz.github.io/), [matplotlib](https://matplotlib.org/), or [plotly](https://plotly.com/)).
    """)
    return


@app.cell
def _(most_shared_websites):
    import altair as alt

    chart = (
        alt.Chart(most_shared_websites)
        .mark_bar()
        .encode(
            x=alt.X("count:Q", title="Number of Shares"),
            y=alt.Y("domain:N", sort="-x", title="Domain"),
            tooltip=["domain", "count"],
        )
        .properties(
            title="Top 20 Most Shared Websites on Hacker News", width="container"
        )
    )

    chart
    return (alt,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Adding reactivity ⚡

    We can also parameterize our SQL using marimo UI elements. This not only makes our SQL reactive, but also any downstream logic, including our charts.
    """)
    return


@app.cell
def _(MONTHS, duckdb, mo):
    month_select = mo.ui.multiselect(
        MONTHS,
        label="Month",
        value=MONTHS.keys(),
    )

    hn_types = duckdb.sql(
        """
        SELECT DISTINCT type as 'HN Type'
        FROM sample_data.hn.hacker_news
        WHERE score IS NOT NULL AND descendants IS NOT NULL
        LIMIT 10;
        """
    ).df()

    hn_type_select = mo.ui.dropdown.from_series(hn_types["HN Type"], value="story")
    return hn_type_select, month_select


@app.cell(hide_code=True)
def _(hn_type_select, mo, month_select):
    month_list = ",".join([str(month) for month in month_select.value])
    mo.hstack(
        [
            mo.md(f"## {mo.icon('lucide:filter')}"),
            month_select,
            hn_type_select,
        ],
    ).left()
    return (month_list,)


@app.cell(hide_code=True)
def _(hn_type_select, mo, month_list):
    most_monthly_voted = mo.sql(
        f"""
        -- Most monthly voted
        -- This query determines the most voted type for each month.
        WITH ranked_stories AS (
            SELECT
                title,
                'https://news.ycombinator.com/item?id=' || id AS hn_url,
                score,
                type,
                descendants,
                YEAR(timestamp) AS year,
                MONTH(timestamp) AS month,
                ROW_NUMBER()
                    OVER (PARTITION BY YEAR(timestamp), MONTH(timestamp) ORDER BY score DESC)
                AS rn
            FROM sample_data.hn.hacker_news
            -- here we parameterize the sql statement
            WHERE
                type = '{hn_type_select.value}'
                AND
                MONTH(timestamp) in ({month_list})
                AND
                descendants IS NOT NULL
        )

        SELECT
            month,
            score,
            type,
            title,
            hn_url,
            descendants as nb_comments,
            year,
        FROM ranked_stories
        WHERE rn = 1
        ORDER BY year, month;
        """
    )
    return (most_monthly_voted,)


@app.cell(hide_code=True)
def _(alt, hn_type_select, most_monthly_voted):
    _chart = (
        alt.Chart(most_monthly_voted)
        .mark_circle()
        .encode(
            x=alt.X("month:O", title="Month"),
            y=alt.Y("score:Q", title="Score"),
            size=alt.Size(
                "nb_comments:Q",
                scale=alt.Scale(range=[100, 1000]),
                title="Number of Comments",
            ),
            color=alt.Color("nb_comments:Q", scale=alt.Scale(scheme="viridis")),
            tooltip=["title", "nb_comments", "hn_url"],
        )
        .properties(
            title=f"Most Commented {hn_type_select.value} Each Month",
            width="container",
            height=400,
        )
    )
    _chart
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Additional Reactivity ⚡⚡
    """)
    return


@app.cell
def _(mo):
    search_input = mo.ui.text(label="Search for keywords", value="duckdb")
    search_input
    return (search_input,)


@app.cell
def _(mo, search_value):
    keyword_results = mo.sql(
        f"""
        SELECT
            YEAR(timestamp) AS year,
            MONTH(timestamp) AS month,
            COUNT(*) AS keyword_mentions
        FROM sample_data.hn.hacker_news
        WHERE
            (title LIKE '%{search_value}%' OR text LIKE '%{search_value}%')
        GROUP BY year, month
        ORDER BY year ASC, month ASC;
        """
    )
    return (keyword_results,)


@app.cell(hide_code=True)
def _(search_input):
    search_value = search_input.value
    return (search_value,)


@app.cell(hide_code=True)
def _(alt, keyword_results, mo, search_value):
    if keyword_results.is_empty():
        mo.stop(True, f"No results for {search_value}")

    # Create the chart
    _chart = (
        alt.Chart(keyword_results)
        .mark_rect()
        .encode(
            x=alt.X("month:O", title="Month"),
            y=alt.Y("keyword_mentions:Q", title="Year"),
            tooltip=["year", "month", "keyword_mentions"],
        )
        .properties(
            title=f'Monthly Mentions of "{search_value}" in Hacker News Posts',
            width="container",
            height=400,
        )
    )

    # Add text labels for the number of mentions
    _text = (
        alt.Chart(keyword_results)
        .mark_text(baseline="bottom", dy=-5)
        .encode(
            x=alt.X("month:O"),
            y=alt.Y("keyword_mentions:Q", title="Year"),
            text=alt.Text("keyword_mentions:Q"),
        )
    )

    _chart + _text
    return


@app.cell(hide_code=True)
def _():
    MONTHS = {
        "January": 1,
        "February": 2,
        "March": 3,
        "April": 4,
        "May": 5,
        "June": 6,
        "July": 7,
        "August": 8,
        "September": 9,
        "October": 10,
        "November": 11,
        "December": 12,
    }
    return (MONTHS,)


if __name__ == "__main__":
    app.run()
