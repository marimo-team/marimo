# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
#     "polars>=1.37.0",
# ]
# ///
# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import polars as pl

    return mo, pl


@app.cell
def _(mo):
    mo.md(r"""
    # Polars SQL engine

    Every SQL cell below runs with `engine="polars"` against Polars frames
    in the notebook. Check that:

    - each result renders as a table, and editing an upstream cell re-runs
      the SQL cells that read it;
    - the 1M-row flights query finishes quickly, since only its aggregate is
      collected;
    - the last two cells show SQL errors, not Python tracebacks.
    """)


@app.cell
def _(pl):
    penguins = pl.read_csv(
        "https://raw.githubusercontent.com/mwaskom/seaborn-data/master/penguins.csv",
        null_values="NA",
    )
    flights = pl.scan_parquet(
        "https://vegafusion-datasets.s3.amazonaws.com/vega/flights_1m.parquet"
    )
    return flights, penguins


@app.cell
def _(mo):
    mo.md(r"""
    ## Query an eager DataFrame
    """)


@app.cell
def _(mo, penguins):
    species_stats = mo.sql(
        f"""
        SELECT
            species,
            count(*) AS penguins,
            round(avg(body_mass_g)) AS avg_mass_g
        FROM penguins
        WHERE body_mass_g IS NOT NULL
        GROUP BY species
        ORDER BY species
        """,
        engine="polars"
    )
    return (species_stats,)


@app.cell
def _(mo):
    mo.md(r"""
    ## Query the result of another SQL cell
    """)


@app.cell
def _(mo, species_stats):
    _df = mo.sql(
        f"""
        SELECT * FROM species_stats WHERE penguins > 100
        """,
        engine="polars"
    )


@app.cell
def _(mo):
    mo.md(r"""
    ## Query a remote LazyFrame

    `flights` scans a 1M-row Parquet file without loading it.
    """)


@app.cell
def _(flights, mo):
    busiest_routes = mo.sql(
        f"""
        SELECT
            origin,
            destination,
            count(*) AS flights,
            round(avg(delay), 1) AS avg_delay
        FROM flights
        GROUP BY origin, destination
        ORDER BY flights DESC, origin, destination
        LIMIT 20
        """,
        engine="polars"
    )
    return (busiest_routes,)


@app.cell
def _(busiest_routes, mo):
    mo.md(f"""
    `busiest_routes` is a `{type(busiest_routes).__name__}`. It's a
    `DataFrame` with the `auto` and `polars` SQL output types, and a
    `LazyFrame` with `lazy-polars` and `native`. Switch the SQL output type
    in the notebook settings to check each one.
    """)


@app.cell
def _(mo):
    mo.md(r"""
    ## React to UI elements
    """)


@app.cell
def _(mo):
    min_mass = mo.ui.slider(2500, 6500, step=250, value=5500, label="Min mass (g)")
    min_mass
    return (min_mass,)


@app.cell
def _(min_mass, mo, penguins):
    _df = mo.sql(
        f"""
        SELECT species, island, sex, body_mass_g
        FROM penguins
        WHERE body_mass_g >= {min_mass.value}
        ORDER BY body_mass_g DESC, species
        """,
        engine="polars"
    )


@app.cell
def _(mo):
    mo.md(r"""
    ## Polars-only syntax

    Backtick identifiers and `SEMI JOIN` aren't valid DuckDB SQL, but the
    cell should still re-run when `islands` changes.
    """)


@app.cell
def _(pl):
    islands = pl.DataFrame({"island": ["Biscoe", "Dream"]})
    return (islands,)


@app.cell
def _(islands, mo, penguins):
    _df = mo.sql(
        f"""
        WITH heavy AS (SELECT * FROM penguins WHERE body_mass_g > 4500)
        SELECT species, island, count(*) AS penguins
        FROM heavy
        SEMI JOIN `islands` USING (island)
        GROUP BY species, island
        ORDER BY species, island
        """,
        engine="polars"
    )


@app.cell
def _(mo):
    mo.md(r"""
    ## Errors

    Both cells should fail with a SQL error.
    """)


@app.cell
def _(mo, penguins):
    _df = mo.sql(
        f"""
        SELECT no_such_column FROM penguins
        """,
        engine="polars"
    )


@app.cell
def _(mo):
    _df = mo.sql(
        f"""
        SELECT * FROM no_such_table
        """,
        engine="polars"
    )


if __name__ == "__main__":
    app.run()
