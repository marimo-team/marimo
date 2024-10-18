import marimo

__generated_with = "0.9.14"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def init():
    import marimo as mo
    import altair as alt
    import polars as pl
    import os

    for csv in os.listdir(mo.notebook_dir() / "data"):
        if csv.endswith(".csv"):
            table_name = csv.split(".")[0]
            print(csv)
            mo.sql(f"""
           CREATE OR REPLACE TABLE {table_name} AS
           FROM read_csv("./data/{csv}");        
            """)
    return alt, csv, mo, os, pl, table_name


@app.cell(hide_code=True)
def debug_schemas(mo, os, pl):
    mo.stop(True)  # Comment out to run and get all the schemas

    # Read files in ./data
    for _file in os.listdir("./data"):
        if _file.endswith(".csv"):
            df = pl.read_csv(
                f"./data/{_file}", infer_schema_length=10000, ignore_errors=True
            )
            print(_file)
            print(df.schema)
    return (df,)


@app.cell
def __(drivers, mo):
    drivers_by_id = mo.sql(
        """
        -- Driver Dropdown List
        SELECT
            driverId,
            CONCAT(forename, ' ', surname) as driver_name
        FROM drivers
        ORDER BY forename, surname;
        """, output=False
    )
    return (drivers_by_id,)


@app.cell
def __(drivers_by_id, mo):
    # drivers_dict = {row[0]: row[1] for row in drivers_by_id.iter_rows()}
    # drivers_dict
    # _options = drivers_by_id
    driver_select = mo.ui.dropdown.from_series(
        drivers_by_id["driver_name"], label="Driver", value="Lewis Hamilton"
    )
    return (driver_select,)


@app.cell
def __(driver_select, drivers_by_id, pl):
    selected_driver_id = drivers_by_id.filter(
        pl.col("driver_name") == driver_select.value
    )[0, 0]
    print(driver_select.value, selected_driver_id)
    return (selected_driver_id,)


@app.cell
def __(constructors, mo, results, selected_driver_id):
    constructor_for_driver = mo.sql(
        f"""
        -- Constructor Filter Options (based on selected driver)
        SELECT DISTINCT 
            c.constructorId,
            c.name as constructor_name
        FROM results r
        JOIN constructors c ON r.constructorId = c.constructorId
        WHERE r.driverId = {selected_driver_id}
        ORDER BY c.name;
        """, output=False
    )
    return (constructor_for_driver,)


@app.cell
def __(mo):
    mo.md(r"""# F1 Series: Driver Career Explorer""")
    return


@app.cell
def __(constructor_select, driver_select, mo):
    mo.hstack(
        [
            driver_select,
            mo.hstack(
                [
                    mo.md("**::lucide:filter:: Filters:**"),
                    constructor_select,
                    # circuit_select,
                ]
            ).left(),
        ]
    )
    return


@app.cell
def __(constructor_for_driver, mo):
    constructor_select = mo.ui.dropdown.from_series(
        constructor_for_driver["constructor_name"],
        label="Constructor",
        value=None,
    )
    return (constructor_select,)


@app.cell
def __(circuit_type, mo):
    circuit_select = mo.ui.dropdown.from_series(
        circuit_type["circuit_name"], label="Circuit", value=None
    )
    return (circuit_select,)


@app.cell
def __(constructor_for_driver, constructor_select, pl):
    if constructor_select.value:
        selected_constructor_id = constructor_for_driver.filter(
            pl.col("constructor_name") == constructor_select.value
        )[0, 0]
    else:
        selected_constructor_id = "NULL"
    print(constructor_select.value, selected_constructor_id)
    return (selected_constructor_id,)


@app.cell
def __(
    constructors,
    mo,
    races,
    results,
    selected_constructor_id,
    selected_driver_id,
):
    total_points_by_season = mo.sql(
        f"""
        -- Points Progression Over Seasons (main line chart):
        SELECT 
            r.year,
            SUM(res.points) as total_points,
            c.name as constructor_name
        FROM races r
        JOIN results res ON r.raceId = res.raceId
        JOIN constructors c ON res.constructorId = c.constructorId
        WHERE res.driverId = {selected_driver_id}
            AND (
                {selected_constructor_id} IS NULL
                OR
                res.constructorId = {selected_constructor_id}
            )
        GROUP BY r.year, c.name
        ORDER BY r.year;
        """, output=False
    )
    return (total_points_by_season,)


@app.cell
def __(
    constructors,
    mo,
    races,
    results,
    selected_constructor_id,
    selected_driver_id,
):
    points_by_race = mo.sql(
        f"""
        -- Drive races
        SELECT 
            r.year,
            res.points,
            r.raceId,
            c.name as constructor_name,
            r.name as race_name,
        FROM races r
        JOIN results res ON r.raceId = res.raceId
        JOIN constructors c ON res.constructorId = c.constructorId
        WHERE res.driverId = {selected_driver_id}
            AND (
                {selected_constructor_id} IS NULL
                OR
                res.constructorId = {selected_constructor_id}
            )
        ORDER BY r.date;
        """, output=False
    )
    return (points_by_race,)


@app.cell
def __(mo, races, results, selected_constructor_id, selected_driver_id):
    career_stats = mo.sql(
        f"""
        -- Career Statistics (stat cards)
        SELECT 
            COUNT(CASE WHEN positionOrder = 1 THEN 1 END) as total_wins,
            COUNT(CASE WHEN positionOrder <= 3 THEN 1 END) as total_podiums,
            COUNT(*) as total_races,
            ROUND(SUM(points), 0) as total_points,
            COUNT(CASE WHEN grid = 1 THEN 1 END) as pole_positions,
            COUNT(CASE WHEN rank = '1' THEN 1 END) as fastest_laps
        FROM results res
        JOIN races r ON res.raceId = r.raceId
        WHERE res.driverId = {selected_driver_id}
            AND ({selected_constructor_id} IS NULL OR res.constructorId = {selected_constructor_id});
        """, output=False
    )
    return (career_stats,)


@app.cell(hide_code=True)
def __(career_stats, constructor_select, driver_select, mo):
    mo.stop(career_stats is None)

    _cards = [
        mo.stat(
            label=label.title().replace("_", " "),
            value=career_stats[label][0],
            bordered=True,
        )
        for label in career_stats.columns
    ]

    _title = f"### **{driver_select.value}**'s Career Statistics"
    if constructor_select.value:
        _title += f" @ _{constructor_select.value}_"

    mo.vstack(
        [
            mo.md(_title),
            mo.hstack(_cards, widths="equal", align="center"),
        ]
    )
    return


@app.cell
def __(mo, season_chart):
    mo.stop(not len(season_chart.value["year"]))
    selected_year = season_chart.value["year"][0]
    return (selected_year,)


@app.cell
def __(mo):
    mo.md(r"""## Season Overview""")
    return


@app.cell
def __(bar_season_chart, mo):
    season_chart = bar_season_chart()
    mo.vstack([season_chart, mo.md("_Select a year on the chart above!_")])
    return (season_chart,)


@app.cell(hide_code=True)
def __(alt, mo, points_by_race, total_points_by_season):
    def bar_season_chart():
        _chart = (
            alt.Chart(total_points_by_season)
            .mark_bar()
            .encode(x="year:O", y="total_points:Q", color="constructor_name:N")
        )

        return mo.ui.altair_chart(
            _chart,
            chart_selection="point",
            legend_selection=False,
            label="Points Progression Over Seasons",
        )


    def dot_season_chart():
        _chart = (
            alt.Chart(points_by_race)
            .mark_circle()
            .encode(
                x="race_name:N",
                y="year:O",
                color="constructor_name:N",
                size="points:Q",
            )
        )

        return mo.ui.altair_chart(
            _chart,
            chart_selection="point",
            legend_selection=False,
            label="Points Progression Over Seasons",
        )
    return bar_season_chart, dot_season_chart


@app.cell
def __(
    mo,
    races,
    results,
    selected_constructor_id,
    selected_driver_id,
    selected_year,
):
    podium_finishes = mo.sql(
        f"""
        -- Podium Finishes for Selected Season Point (bar chart)
        SELECT 
            COUNT(CASE WHEN positionOrder = 1 THEN 1 END) as wins,
            COUNT(CASE WHEN positionOrder = 2 THEN 1 END) as seconds,
            COUNT(CASE WHEN positionOrder = 3 THEN 1 END) as thirds
        FROM results res
        JOIN races r ON res.raceId = r.raceId
        WHERE res.driverId = {selected_driver_id}
            AND r.year = {selected_year}
            AND ({selected_constructor_id} IS NULL OR res.constructorId = {selected_constructor_id});
        """, output=False
    )
    return (podium_finishes,)


@app.cell(hide_code=True)
def __(alt, pl, podium_finishes):
    _data = pl.DataFrame(
        {
            "Position": ["🥇 Wins", "🥈 Seconds", "🥉 Thirds"],
            "Count": [
                podium_finishes["wins"][0],
                podium_finishes["seconds"][0],
                podium_finishes["thirds"][0],
            ],
        }
    )

    # Create a bar chart with text labels
    podium_chart = (
        alt.Chart(_data)
        .mark_bar()
        .encode(
            x=alt.X("Position", sort=None),
            y="Count",
            color=alt.Color("Position", scale=alt.Scale(scheme="set1")),
        )
        .properties(title="Podium Finishes", width="container")
    )

    # Add text labels
    _text = podium_chart.mark_text(
        align="center",
        baseline="bottom",
        size=20,
        dy=-5,  # Nudge text upward so it doesn't overlap with the top of the bar
    ).encode(text="Count")

    # Combine the chart and the text
    podium_chart += _text
    return (podium_chart,)


@app.cell(hide_code=True)
def __(
    mo,
    races,
    results,
    selected_constructor_id,
    selected_driver_id,
    selected_year,
    status,
):
    dnf_reasons = mo.sql(
        f"""
        -- DNF Reasons Distribution (pie chart)
        SELECT 
            s.status,
            COUNT(*) as count
        FROM results res
        JOIN races r ON res.raceId = r.raceId
        JOIN status s ON res.statusId = s.statusId
        WHERE res.driverId = {selected_driver_id}
            AND r.year = {selected_year}
            AND ({selected_constructor_id} IS NULL OR res.constructorId = {selected_constructor_id})
            AND s.status NOT IN ('Finished', '+1 Lap', '+2 Laps', '+3 Laps', '+4 Laps')
        GROUP BY s.status
        ORDER BY count DESC;
        """, output=False
    )
    return (dnf_reasons,)


@app.cell(hide_code=True)
def __(alt, dnf_reasons, mo):
    # Create a pie chart
    pie_chart = (
        (
            alt.Chart(dnf_reasons)
            .mark_arc()
            .encode(
                theta=alt.Theta(field="count", type="quantitative"),
                color=alt.Color(field="status", type="nominal", legend=None),
                tooltip=["status", "count"],
            )
            .properties(title="DNF Reasons", width="container")
        )
        if dnf_reasons is not None
        else mo.md("No DNFs for this season!").callout().center()
    )
    return (pie_chart,)


@app.cell
def __(mo, pie_chart, podium_chart):
    mo.hstack([podium_chart, pie_chart], widths="equal", align="center")
    return


@app.cell(hide_code=True)
def __(
    mo,
    qualifying,
    races,
    results,
    selected_constructor_id,
    selected_driver_id,
    selected_year,
):
    qualifying_vs_race_positions = mo.sql(
        f"""
        -- Qualifying vs Race Position Comparison
        SELECT
            r.name as race_name,
            q.position as qualifying_position,
            res.positionOrder as race_position
        FROM races r
        JOIN qualifying q ON r.raceId = q.raceId
        JOIN results res ON r.raceId = res.raceId AND q.driverId = res.driverId
        WHERE res.driverId = {selected_driver_id}
            AND r.year = {selected_year}
            AND ({selected_constructor_id} IS NULL OR res.constructorId = {selected_constructor_id})
        ORDER BY r.date;
        """, output=False
    )
    return (qualifying_vs_race_positions,)


@app.cell(hide_code=True)
def __(alt, qualifying_vs_race_positions):
    base = alt.Chart(qualifying_vs_race_positions).encode(
        x=alt.X("race_name:N", axis=alt.Axis(labelAngle=20)).title(None),
    )

    area = base.mark_line(stroke="#57A44C", interpolate="monotone").encode(
        alt.Y("qualifying_position").title(
            "Qualifying Position", titleColor="#57A44C"
        ),
    )

    line = base.mark_line(stroke="#5276A7", interpolate="monotone").encode(
        alt.Y("race_position").title("Race Position", titleColor="#5276A7")
    )

    alt.layer(area, line).resolve_scale(y="independent").properties(
        width="container", title="Pole Positions"
    )
    return area, base, line


@app.cell
def __(circuits, mo, races, results, selected_driver_id):
    circuit_type = mo.sql(
        f"""
        -- Circuit Filter Data
        SELECT DISTINCT 
            c.circuitId,
            c.name as circuit_name,
            c.country
        FROM circuits c
        JOIN races r ON c.circuitId = r.circuitId
        JOIN results res ON r.raceId = res.raceId
        WHERE res.driverId = {selected_driver_id}
            -- AND r.year BETWEEN start_year AND end_year
        ORDER BY c.name;
        """, output=False
    )
    return (circuit_type,)


@app.cell
def __(mo, selected_constructor_id, selected_driver_id):
    _df = mo.sql(
        f"""
        -- WITH FastestLapDetails AS (
        --     SELECT 
        --         r.year,
        --         r.name as race_name,
        --         res.fastestLapTime,
        --         res.fastestLapSpeed,
        --         c.name as constructor_name,
        --         RANK() OVER (PARTITION BY r.raceId ORDER BY res.fastestLapTime) as lap_rank
        --     FROM results res
        --     JOIN races r ON res.raceId = r.raceId
        --     JOIN constructors c ON res.constructorId = c.constructorId
        --     WHERE res.driverId = {selected_driver_id}
        --         AND res.fastestLapTime IS NOT NULL
        --         -- AND r.year BETWEEN start_year AND end_year
        --         AND ({selected_constructor_id} IS NULL OR res.constructorId = {selected_constructor_id})
        -- )
        -- SELECT 
        --     year,
        --     race_name,
        --     fastestLapTime,
        --     fastestLapSpeed,
        --     constructor_name,
        --     CASE 
        --         WHEN lap_rank = 1 THEN 'Fastest Overall'
        --         WHEN lap_rank <= 3 THEN 'Top 3'
        --         ELSE 'Other'
        --     END as lap_achievement
        -- FROM FastestLapDetails
        -- ORDER BY year, race_name;
        """
    )
    return


@app.cell
def __(mo, selected_constructor_id, selected_driver_id):
    _df = mo.sql(
        f"""
        -- SELECT 
        --     COUNT(CASE WHEN lap_rank = 1 THEN 1 END) as total_fastest_laps,
        --     COUNT(CASE WHEN lap_rank <= 3 THEN 1 END) as total_top3_fastest_laps,
        --     ROUND(AVG(CAST(fastestLapSpeed AS FLOAT)), 2) as avg_fastest_lap_speed
        -- FROM (
        --     SELECT 
        --         res.fastestLapSpeed,
        --         RANK() OVER (PARTITION BY r.raceId ORDER BY res.fastestLapTime) as lap_rank
        --     FROM results res
        --     JOIN races r ON res.raceId = r.raceId
        --     WHERE res.driverId = {selected_driver_id}
        --         AND res.fastestLapTime IS NOT NULL
        --         AND ({selected_constructor_id} IS NULL OR res.constructorId = {selected_constructor_id})
        -- ) subquery;
        """
    )
    return


@app.cell
def __(mo):
    mo.md(r"""## Race Drilldown""")
    return


@app.cell
def __(dot_season_chart):
    race_drilldown_chart = dot_season_chart()
    race_drilldown_chart
    return (race_drilldown_chart,)


@app.cell
def __(mo, race_drilldown_chart):
    mo.stop(race_drilldown_chart is None)
    _series = race_drilldown_chart.value["raceId"]
    mo.stop(len(_series) < 1)
    selected_race_id = race_drilldown_chart.value["raceId"][0]
    print(selected_race_id)
    return (selected_race_id,)


@app.cell
def __(
    LapAnalysis,
    PitStopInfo,
    constructors,
    lap_times,
    mo,
    pit_stops,
    qualifying,
    races,
    results,
    selected_driver_id,
    selected_race_id,
    status,
):
    race_stats = mo.sql(
        f"""
        WITH LapAnalysis AS (
            SELECT 
                lap,
                position,
                time as lap_time,
                milliseconds,
                LAG(position) OVER (ORDER BY lap) as prev_position,
                ROW_NUMBER() OVER (ORDER BY milliseconds) as fastest_lap_rank
            FROM lap_times
            WHERE raceId = {selected_race_id} 
            AND driverId = {selected_driver_id}
        ),
        PitStopInfo AS (
            SELECT 
                lap as pit_lap,
                duration,
                stop as pit_stop_number
            FROM pit_stops
            WHERE raceId = {selected_race_id}
            AND driverId = {selected_driver_id}
        )
        SELECT 
            -- Basic Race Info
            r.name as race_name,
            r.date as race_date,
            c.name as constructor_name,

            -- Starting & Finishing Position
            res.grid as start_position,
            res.positionOrder as finish_position,

            -- Qualifying Performance
            q.q1 as qualifying_1,
            q.q2 as qualifying_2,
            q.q3 as qualifying_3,
            q.position as qualifying_position,

            -- Race Statistics
            res.points as points_earned,
            res.laps as laps_completed,
            res.time as race_time,
            res.fastestLapTime as fastest_lap_time,
            res.fastestLapSpeed as fastest_lap_speed,
            s.status as race_status,

            -- Detailed Lap Information
            (SELECT COUNT(*) FROM LapAnalysis WHERE position < prev_position) as positions_lost,
            (SELECT COUNT(*) FROM LapAnalysis WHERE position > prev_position) as positions_gained,
            (SELECT MIN(milliseconds) FROM LapAnalysis) as best_lap_time_ms,
            (SELECT AVG(milliseconds) FROM LapAnalysis) as avg_lap_time_ms,
            (SELECT MAX(milliseconds) FROM LapAnalysis) as worst_lap_time_ms,

            -- Pit Stop Summary
            (SELECT COUNT(*) FROM PitStopInfo) as total_pit_stops,
            (SELECT AVG(CAST(duration as FLOAT)) FROM PitStopInfo) as avg_pit_stop_duration,

            -- Detailed Arrays for Visualization
            (SELECT array_agg(lap_time ORDER BY lap) FROM LapAnalysis) as lap_times_array,
            (SELECT array_agg(position ORDER BY lap) FROM LapAnalysis) as positions_array,
            (SELECT array_agg(pit_lap ORDER BY pit_lap) FROM PitStopInfo) as pit_stop_laps_array,

            -- Race Context
            (SELECT COUNT(*) FROM results WHERE raceId = {selected_race_id}) as total_drivers_in_race,

            -- Weather/Track Condition Proxy
            (SELECT COUNT(DISTINCT driverId) 
             FROM results 
             WHERE raceId = {selected_race_id} AND statusId IN 
                (SELECT statusId FROM status WHERE status LIKE '%crash%' OR status LIKE '%spun%')
            ) as incidents_count

        FROM races r
        JOIN results res ON r.raceId = res.raceId
        JOIN constructors c ON res.constructorId = c.constructorId
        JOIN status s ON res.statusId = s.statusId
        LEFT JOIN qualifying q ON r.raceId = q.raceId AND q.driverId = res.driverId
        WHERE r.raceId = {selected_race_id}
        AND res.driverId = {selected_driver_id};
        """, output=False
    )
    return (race_stats,)


@app.cell
def __(mo, race_stats):
    _left = mo.md(f"""
    **Date:** {race_stats['race_date'][0].strftime('%B %d, %Y')}  
    **Circuit:** {race_stats['constructor_name'][0]}  
    **Start Position:** {race_stats['start_position'][0]}  
    **Finish Position:** {race_stats['finish_position'][0]}  
    **Points Earned:** {race_stats['points_earned'][0]}  
    """)

    _right = mo.md(f"""
    **Laps Completed:** {race_stats['laps_completed'][0]}  
    **Race Time:** {race_stats['race_time'][0]}  
    **Fastest Lap Time:** {race_stats['fastest_lap_time'][0]}  
    **Fastest Lap Speed:** {race_stats['fastest_lap_speed'][0]}  
    **Race Status:** {race_stats['race_status'][0]}  
    """).right()

    _header = mo.md(f"""
    ## Race Overview: {race_stats['race_name'][0]}

    {mo.hstack([_left, _right], widths="equal")}
    """)

    _cards = [
        mo.stat(
            label="Positions Gained",
            value=race_stats["positions_gained"][0],
            bordered=True,
        ).style(min_width="300px"),
        mo.stat(
            label="Positions Lost",
            value=race_stats["positions_lost"][0],
            bordered=True,
        ).style(min_width="300px"),
        mo.stat(
            label="Best Lap Time (ms)",
            value=race_stats["best_lap_time_ms"][0],
            bordered=True,
        ).style(min_width="300px"),
        mo.stat(
            label="Average Lap Time (ms)",
            value=race_stats["avg_lap_time_ms"][0],
            bordered=True,
        ).style(min_width="300px"),
        mo.stat(
            label="Worst Lap Time (ms)",
            value=race_stats["worst_lap_time_ms"][0],
            bordered=True,
        ).style(min_width="300px"),
        mo.stat(
            label="Total Pit Stops",
            value=race_stats["total_pit_stops"][0],
            bordered=True,
        ).style(min_width="300px"),
        mo.stat(
            label="Average Pit Stop Duration",
            value=race_stats["avg_pit_stop_duration"][0],
            bordered=True,
        ).style(min_width="300px"),
        mo.stat(
            label="Total Drivers in Race",
            value=race_stats["total_drivers_in_race"][0],
            bordered=True,
        ).style(min_width="300px"),
        mo.stat(
            label="Incidents Count",
            value=race_stats["incidents_count"][0],
            bordered=True,
        ).style(min_width="300px"),
    ]

    mo.vstack(
        [
            _header,
            mo.hstack(_cards, align="center", justify="space-around", wrap=True),
        ]
    )
    return


if __name__ == "__main__":
    app.run()
