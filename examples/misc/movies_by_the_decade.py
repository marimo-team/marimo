import marimo

__generated_with = "0.1.33"
app = marimo.App(width="full")


@app.cell
def __(
    button_00s,
    button_10s,
    button_80s,
    button_90s,
    end_date,
    mo,
    start_date,
):
    _range = mo.md(f"{start_date} - {end_date}")

    mo.hstack(
        [
            _range,
            mo.hstack(
                [
                    mo.md("Quick decade:"),
                    button_80s,
                    button_90s,
                    button_00s,
                    button_10s,
                ]
            ),
        ]
    )
    return


@app.cell
def __(mo, pd, set_end_date, set_start_date):
    def decade_button(decade):
        s = pd.to_datetime(f"{decade}-01-01")
        e = pd.to_datetime(f"{decade + 10}-01-01")

        def handle_click(v):
            set_start_date(s)
            set_end_date(e)
            return 1

        return mo.ui.button(
            label=f"{decade}s",
            on_click=handle_click,
        )


    button_80s = decade_button(1980)
    button_90s = decade_button(1990)
    button_00s = decade_button(2000)
    button_10s = decade_button(2010)
    return button_00s, button_10s, button_80s, button_90s, decade_button


@app.cell
def __(mo, previous_end_date, previous_start_date):
    mo.md(
        f"""
    > Compared to: {previous_start_date.strftime("%Y-%m-%d")} - {previous_end_date.strftime("%Y-%m-%d")}
    """
    )
    return


@app.cell
def __(get_end_date, get_start_date, mo, pd, set_end_date, set_start_date):
    start_date = mo.ui.date(
        label="Start Date",
        value=get_start_date().strftime("%Y-%m-%d"),
        on_change=lambda x: set_start_date(pd.to_datetime(x)),
    )
    end_date = mo.ui.date(
        label="End Date",
        value=get_end_date().strftime("%Y-%m-%d"),
        on_change=lambda x: set_end_date(pd.to_datetime(x)),
    )
    return end_date, start_date


@app.cell
def __(
    filtered_movies,
    get_average_budget,
    get_average_gross,
    get_average_rating,
    get_average_runtime,
    mo,
    previous_movies,
):
    mo.stop(len(filtered_movies) == 0, "")

    previous_total_movies_count = len(previous_movies)
    previous_total_movies_change_rate = (
        (len(filtered_movies) - previous_total_movies_count)
        / previous_total_movies_count
        if previous_total_movies_count > 0
        else 0
    )
    total_movies = mo.stat(
        label="Total Movies",
        bordered=True,
        caption=f"{previous_total_movies_change_rate:.0%}",
        direction="increase"
        if previous_total_movies_change_rate > 0
        else "decrease",
        value=f"{len(filtered_movies):,.0f}",
    )

    gross_current, gross_previous, gross_rate = get_average_gross(
        filtered_movies, previous_movies
    )
    gross_stat = mo.stat(
        label="Average Gross",
        bordered=True,
        caption=f"{gross_rate:.0%}",
        direction="increase" if gross_rate > 0 else "decrease",
        value=f"${gross_current:,.0f}",
    )

    budget_current, budget_previous, budget_rate = get_average_budget(
        filtered_movies, previous_movies
    )
    budget_stat = mo.stat(
        label="Average Budget",
        bordered=True,
        caption=f"{budget_rate:.0%}",
        direction="increase" if budget_rate > 0 else "decrease",
        value=f"${budget_current:,.0f}",
    )

    runtime_current, runtime_previous, runtime_rate = get_average_runtime(
        filtered_movies, previous_movies
    )
    runtime_stat = mo.stat(
        label="Average Runtime",
        bordered=True,
        caption=f"{runtime_rate:.0%}",
        direction="increase" if runtime_rate > 0 else "decrease",
        value=f"{runtime_current:,.0f} min",
    )

    rating_current, rating_previous, rating_rate = get_average_rating(
        filtered_movies, previous_movies
    )
    average_rating = mo.stat(
        label="Average Rating",
        bordered=True,
        caption=f"{rating_rate:.0%}",
        direction="increase" if rating_rate > 0 else "decrease",
        value=f"{rating_current:.1f}",
    )

    mo.hstack(
        [total_movies, gross_stat, budget_stat, runtime_stat, average_rating],
        widths="equal",
        gap=1,
    )
    return (
        average_rating,
        budget_current,
        budget_previous,
        budget_rate,
        budget_stat,
        gross_current,
        gross_previous,
        gross_rate,
        gross_stat,
        previous_total_movies_change_rate,
        previous_total_movies_count,
        rating_current,
        rating_previous,
        rating_rate,
        runtime_current,
        runtime_previous,
        runtime_rate,
        runtime_stat,
        total_movies,
    )


@app.cell
def __(filtered_movies, mo):
    mo.ui.tabs(
        {
            "📑 Data": mo.ui.table(filtered_movies, selection=None, page_size=5),
            "📊 Summary": mo.ui.table(filtered_movies.describe(), selection=None),
        }
    )
    return


@app.cell
def __(alt, filtered_movies, mo):
    # chart of rating by budget
    _chart = (
        alt.Chart(filtered_movies)
        .mark_circle()
        .encode(
            x="Production_Budget",
            y="IMDB_Rating",
            color="Major_Genre",
            tooltip=[
                "Title",
                "Production_Budget",
                "Worldwide_Gross",
                "IMDB_Rating",
                "Major_Genre",
            ],
        )
    )
    chart = mo.ui.altair_chart(_chart)
    chart
    return chart,


@app.cell
def __(
    chart,
    get_average_budget,
    get_average_gross,
    get_average_rating,
    get_average_runtime,
    mo,
):
    mo.stop(len(chart.value) == 0, mo.callout("Select data to view stats."))

    _total_movies = mo.stat(
        label="Total Movies",
        value=f"{len(chart.value):,.0f}",
    )

    _gross_current, _, _ = get_average_gross(chart.value, chart.value)
    _gross_stat = mo.stat(
        label="Average Gross",
        value=f"${_gross_current:,.0f}",
    )

    _budget_current, _, _ = get_average_budget(chart.value, chart.value)
    _budget_stat = mo.stat(
        label="Average Budget",
        value=f"${_budget_current:,.0f}",
    )

    _runtime_current, _, _ = get_average_runtime(chart.value, chart.value)
    _runtime_stat = mo.stat(
        label="Average Runtime",
        value=f"{_runtime_current:,.0f} min",
    )

    _rating_current, _, _ = get_average_rating(chart.value, chart.value)
    _average_rating = mo.stat(
        label="Average Rating",
        value=f"{_rating_current:.1f}",
    )

    mo.hstack(
        [_total_movies, _gross_stat, _budget_stat, _runtime_stat, _average_rating],
        widths="equal",
        gap=1,
    )
    return


@app.cell
def __(alt, filtered_movies, mo):
    # chart of ratings by genre
    # colored by decade
    _bar_chart = (
        alt.Chart(filtered_movies)
        .mark_bar()
        .encode(
            x=alt.X("Major_Genre", sort="-y"),
            y="count()",
            color=alt.Color("Release_Date", scale=alt.Scale(scheme="viridis")),
            tooltip=["Major_Genre", "count()"],
        )
    )
    bar_chart = mo.ui.altair_chart(_bar_chart)
    bar_chart
    return bar_chart,


@app.cell
def __(datetime):
    def get_average_budget(df, previous):
        current = df["US_Gross"].mean()
        previous = previous["US_Gross"].mean()
        rate = (current - previous) / previous
        return (current, previous, rate)


    def get_average_gross(df, previous):
        current = df["Worldwide_Gross"].mean()
        previous = previous["Worldwide_Gross"].mean()
        rate = (current - previous) / previous
        return (current, previous, rate)


    def get_average_runtime(df, previous):
        current = df["Running_Time_min"].mean()
        previous = previous["Running_Time_min"].mean()
        rate = (current - previous) / previous
        return (current, previous, rate)


    def get_average_rating(df, previous):
        current = df["IMDB_Rating"].mean()
        previous = previous["IMDB_Rating"].mean()
        rate = (current - previous) / previous
        return (current, previous, rate)


    def get_previous_date_range(start_date, end_date):
        delta = end_date - start_date
        return (
            (start_date - datetime.timedelta(days=delta.days)),
            (end_date - datetime.timedelta(days=delta.days)),
        )


    def format_date(date):
        return date.strftime("%Y-%m-%d")
    return (
        format_date,
        get_average_budget,
        get_average_gross,
        get_average_rating,
        get_average_runtime,
        get_previous_date_range,
    )


@app.cell
def __():
    import marimo as mo
    import vega_datasets as data
    import time
    import pandas as pd
    import datetime
    import altair as alt
    return alt, data, datetime, mo, pd, time


@app.cell
def __(data, pd):
    movies = data.data.movies()

    # convert to date
    movies["Release_Date"] = pd.to_datetime(movies["Release_Date"])
    return movies,


@app.cell
def __(mo, pd):
    # min = movies["Release_Date"].min()
    # max = movies["Release_Date"].max()
    min = "2010-01-01"
    max = "2021-01-01"
    get_start_date, set_start_date = mo.state(pd.to_datetime(min))
    get_end_date, set_end_date = mo.state(pd.to_datetime(max))
    return (
        get_end_date,
        get_start_date,
        max,
        min,
        set_end_date,
        set_start_date,
    )


@app.cell
def __(end_date, get_previous_date_range, movies, pd, start_date):
    start = pd.to_datetime(start_date.value)
    end = pd.to_datetime(end_date.value)
    filtered_movies = movies[
        (movies["Release_Date"] >= start) & (movies["Release_Date"] <= end)
    ]
    try:
        previous_start_date, previous_end_date = get_previous_date_range(
            start, end
        )
        previous_movies = movies[
            (movies["Release_Date"] >= previous_start_date)
            & (movies["Release_Date"] <= previous_end_date)
        ]
    except:
        previous_start_date = start
        previous_end_date = end
        previous_movies = filtered_movies
    return (
        end,
        filtered_movies,
        previous_end_date,
        previous_movies,
        previous_start_date,
        start,
    )


@app.cell
def __():
    return


if __name__ == "__main__":
    app.run()
