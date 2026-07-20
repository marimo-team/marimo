# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
#     "pandas",
#     "pint",
#     "pint-pandas==0.8.0",
#     "awkward-pandas",
#     "awkward",
# ]
# ///

import marimo

__generated_with = "0.23.10"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    # Pandas extension-array table display

    Smoke test for rich table rendering of pandas extension dtypes.

    Related: [marimo#9947](https://github.com/marimo-team/marimo/issues/9947)

    Each section shows the default rich table output. Values should be
    human-readable (e.g. `1.0 meter` for pint-pandas), not nested JSON blobs.

    Use `mo.plain(...)` beside each example to compare against plain HTML.
    """)
    return


@app.cell
def _():
    import marimo as mo
    import pandas as pd
    import pint
    from decimal import Decimal

    import awkward as ak
    import awkward_pandas as akpd
    import pint_pandas  # noqa: F401 — registers pint dtypes with pandas

    return Decimal, ak, akpd, mo, pd, pint


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## pint-pandas (float magnitudes)

    Expect readable quantities like `1.0 meter`.
    """)
    return


@app.cell
def _(mo, pd):
    pint_float_series = pd.Series([1, 2, 3, 4], dtype="pint[meter]")
    pint_float_df = pd.DataFrame(
        {
            "length": pint_float_series,
            "width": pd.Series([0.5, 1.0, 1.5, 2.0], dtype="pint[meter]"),
        }
    )
    mo.vstack(
        [
            mo.md("**Series**"),
            mo.hstack(
                [mo.plain(pint_float_series), pint_float_series], widths="equal"
            ),
            mo.md("**DataFrame**"),
            mo.hstack([mo.plain(pint_float_df), pint_float_df], widths="equal"),
        ]
    )
    return (pint_float_series,)


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## pint-pandas (from `Decimal` source values)

    Constructed from `decimal.Decimal` inputs before casting to `pint[meter]`.
    """)
    return


@app.cell
def _(Decimal, mo, pd):
    decimal_lengths = pd.Series(
        [Decimal("1.5"), Decimal("2.25"), Decimal("3.125"), Decimal("4.0"), 1 / 3]
    )
    pint_from_decimal = decimal_lengths.astype("pint[meter]")
    pint_decimal_df = pd.DataFrame(
        {
            "raw_decimal": decimal_lengths,
            "length": pint_from_decimal,
        }
    )
    mo.vstack(
        [
            mo.md("**Series (from Decimal → pint)**"),
            mo.hstack(
                [mo.plain(pint_from_decimal), pint_from_decimal], widths="equal"
            ),
            mo.md("**DataFrame (raw decimal + pint column)**"),
            mo.hstack(
                [mo.plain(pint_decimal_df), pint_decimal_df], widths="equal"
            ),
        ]
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## awkward-pandas

    Numeric awkward arrays should stay numeric in the table (not stringified).
    """)
    return


@app.cell
def _(ak, akpd, mo, pd):
    awkward_numeric = pd.Series(
        akpd.AwkwardExtensionArray(ak.Array([1.1, 2.2, 3.3, 4.4]))
    )
    awkward_struct = pd.Series(
        akpd.AwkwardExtensionArray(
            ak.Array([{"x": 1, "y": 2}, {"x": 3, "y": 4}, {"x": 5, "y": 6}])
        )
    )
    awkward_df = pd.DataFrame(
        {
            "values": awkward_numeric,
            "records": awkward_struct,
        }
    )
    mo.vstack(
        [
            mo.md("**Numeric awkward Series**"),
            mo.hstack(
                [mo.plain(awkward_numeric), awkward_numeric], widths="equal"
            ),
            mo.md("**Struct awkward Series**"),
            mo.hstack([mo.plain(awkward_struct), awkward_struct], widths="equal"),
            mo.md("**DataFrame**"),
            mo.hstack([mo.plain(awkward_df), awkward_df], widths="equal"),
        ]
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Object column of bare `pint.Quantity`

    Expect readable values like `1 second`, not nested `_magnitude`/`_units` dicts.
    """)
    return


@app.cell
def _(mo, pd, pint):
    quantity_object_series = pd.Series(
        [
            pint.Quantity("1 sec"),
            pint.Quantity("3 min"),
            pint.Quantity("0.3 hours"),
            pint.Quantity("0.02 days"),
        ]
    )
    quantity_object_df = pd.DataFrame(
        {
            "regular": [1, 2, 3, 7 / 9],
            "meters": pd.Series([1, 2, 3, 7 / 9], dtype="pint[meter]"),
            "mixed": quantity_object_series,
        }
    )
    mo.vstack(
        [
            mo.md("**Series (object dtype)**"),
            mo.hstack(
                [mo.plain(quantity_object_series), quantity_object_series],
                widths="equal",
            ),
            mo.md("**DataFrame (pint dtype + object Quantity column)**"),
            mo.hstack(
                [mo.plain(quantity_object_df), quantity_object_df],
                widths="equal",
            ),
        ]
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Mixed: pint column beside ordinary columns
    """)
    return


@app.cell
def _(mo, pd, pint_float_series):
    mixed_df = pd.DataFrame(
        {
            "id": [1, 2, 3, 4],
            "label": ["a", "b", "c", "d"],
            "length": pint_float_series,
            "count": pd.Series([10, 20, 30, 40], dtype="Int64"),
        }
    )
    mo.hstack([mo.plain(mixed_df), mixed_df], widths="equal")
    return


if __name__ == "__main__":
    app.run()
