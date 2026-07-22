# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "marimo",
#     "pandas",
#     "pint",
#     "pint-pandas",
# ]
# ///

import marimo

__generated_with = "0.23.14"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    # Pint table / JSON display

    Smoke test for pint values in rich tables and other JSON-encoded outputs.

    Related: [marimo#9947](https://github.com/marimo-team/marimo/issues/9947)

    Values should be human-readable (e.g. `1.0 meter`, `1 second`), not nested
    `_magnitude` / `_units` / `_non_int_type` blobs.
    """)
    return


@app.cell
def _():
    import marimo as mo
    import pandas as pd
    import pint
    import pint_pandas  # noqa: F401 — registers pint dtypes with pandas

    return mo, pd, pint


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## DataFrame: pint dtype + object `Quantity` column

    `meters` uses `pint[meter]`; `mixed` is object-dtype bare `pint.Quantity`.
    """)
    return


@app.cell
def _(mo, pd, pint):
    df_mixed = pd.DataFrame(
        data={
            "regular": [1, 2, 3, 7 / 9],
            "meters": pd.Series([1, 2, 3, 7 / 9], dtype="pint[meter]"),
            "mixed": [
                pint.Quantity("1 sec"),
                pint.Quantity("3 min"),
                pint.Quantity("0.3 hours"),
                pint.Quantity("0.02 days"),
            ],
        }
    )
    mo.vstack([df_mixed, mo.plain(df_mixed)])
    return (df_mixed,)


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Computed pint-pandas columns
    """)
    return


@app.cell
def _(mo, pd):
    df_power = pd.DataFrame(
        {
            "torque": pd.Series([1, 2, 2, 3], dtype="pint[lbf ft]"),
            "angular_velocity": pd.Series([1, 2, 2, 3], dtype="pint[rpm]"),
        }
    )
    df_power["power"] = df_power["torque"] * df_power["angular_velocity"]
    mo.vstack([df_power, mo.plain(df_power), df_power.dtypes])
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Global JSON encoding (not just DataFrames)

    Bare pint values and containers that go through `enc_hook` / default tables.
    Expect readable strings, not nested dict dumps.
    """)
    return


@app.cell
def _(mo, pint):
    quantity = pint.Quantity("1.5 meter")
    unit = pint.Unit("second")
    units_container = quantity._units

    mo.vstack(
        [
            mo.md("**Bare `Quantity` / `Unit` / `UnitsContainer`**"),
            mo.hstack(
                [quantity, unit, units_container],
                justify="start",
                gap=2,
            ),
            mo.md("**`mo.plain(...)`**"),
            mo.hstack(
                [
                    mo.plain(quantity),
                    mo.plain(unit),
                    mo.plain(units_container),
                ],
                justify="start",
                gap=2,
            ),
            mo.md("**Default table from list-of-dicts (uses `enc_hook`)**"),
            [
                {"label": "length", "value": quantity},
                {"label": "time unit", "value": unit},
                {"label": "units container", "value": units_container},
                {"label": "duration", "value": pint.Quantity("3 min")},
            ],
        ]
    )
    return


if __name__ == "__main__":
    app.run()
