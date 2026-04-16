import marimo

__generated_with = "0.23.1"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    # Sentinel Values in Tables

    Tables should visually distinguish sentinel values (null, empty string,
    whitespace-only strings, NaN, ±Infinity, NaT) from normal data.

    Each framework has its own semantics — this notebook exercises the
    rendering across Polars, Pandas (object dtype), and Pandas nullable
    dtypes.

    ## Expected rendering
    - `None` / null → muted italic pill labeled `None`
    - Empty string `"\"` → blank in cell, `<empty>` pill in filter dropdown
    - Whitespace (` `, `\t`, `\n`) → visible markers in a pill
    - `NaN` / `inf` / `-inf` → muted pills
    - `NaT` (pandas) → muted pill labeled `NaT` in datetime columns
    - Literal string `"null"`, `"NaN"`, etc. → rendered as normal text
    """)
    return


@app.cell
def _():
    import marimo as mo
    import polars as pl
    import pandas as pd

    return mo, pd, pl


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Polars

    Polars cleanly separates `null` (missing) from `NaN` (a real float value).
    `is_null()` returns `False` for `NaN` — it's a value, not missing.
    Expect `NaN` to render with a pill (it's a special float), distinct from `null`.
    """)
    return


@app.cell(hide_code=True)
def _(mo, pl):
    import datetime as _dt

    df = pl.DataFrame(
        {
            "string_value": [
                "",
                None,
                "NULL",
                "null",
                " ",
                "   ",
                "\t",
                "\n",
                "\t \n",
            ],
            "str_description": [
                "empty string",
                "None",
                "string 'NULL'",
                "string 'null'",
                "single space",
                "three spaces",
                "tab",
                "newline",
                "tab + space + newline",
            ],
            "numeric_value": [
                1.0,
                None,
                float("nan"),
                float("inf"),
                float("-inf"),
                0.0,
                42.0,
                -1.5,
                100.0,
            ],
            "num_description": [
                "1.0",
                "None (null)",
                "NaN (value in polars)",
                "inf",
                "-inf",
                "0.0",
                "42.0",
                "-1.5",
                "100.0",
            ],
            "datetime_value": [
                _dt.datetime(2024, 1, 1),
                None,
                None,
                _dt.datetime(2024, 3, 15),
                _dt.datetime(2024, 4, 20),
                _dt.datetime(2024, 5, 10),
                _dt.datetime(2024, 6, 1),
                _dt.datetime(2024, 7, 4),
                _dt.datetime(2024, 8, 15),
            ],
            "dt_description": [
                "normal",
                "None \u2192 null",
                "None \u2192 null",
                "normal",
                "normal",
                "normal",
                "normal",
                "normal",
                "normal",
            ],
        }
    )
    mo.vstack([mo.md("### Polars"), mo.ui.table(selection=None, data=df)])
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Pandas (classic, object dtype)

    **Caveats:**
    - `None` in a float column is coerced to `NaN`
    - `NaN` is pandas' sentinel for missing in float columns — no way to
      distinguish "missing" from "computational NaN"
    - Missing datetime values are `NaT` (Not a Time), a separate sentinel
    """)
    return


@app.cell(hide_code=True)
def _(mo, pd):
    pdf_classic = pd.DataFrame(
        {
            "string_value": [
                "",
                None,
                "NULL",
                "null",
                " ",
                "   ",
                "\t",
                "\n",
                "\t \n",
            ],
            "str_description": [
                "empty string",
                "None (becomes NaN)",
                "string 'NULL'",
                "string 'null'",
                "single space",
                "three spaces",
                "tab",
                "newline",
                "tab + space + newline",
            ],
            "numeric_value": [
                1.0,
                None,
                float("nan"),
                float("inf"),
                float("-inf"),
                0.0,
                42.0,
                -1.5,
                100.0,
            ],
            "num_description": [
                "1.0",
                "None (becomes NaN)",
                "NaN (missing in pandas)",
                "inf",
                "-inf",
                "0.0",
                "42.0",
                "-1.5",
                "100.0",
            ],
            "datetime_value": pd.to_datetime(
                [
                    "2024-01-01",
                    None,
                    pd.NaT,
                    "2024-03-15",
                    "2024-04-20",
                    "2024-05-10",
                    "2024-06-01",
                    "2024-07-04",
                    "2024-08-15",
                ]
            ),
            "dt_description": [
                "normal date",
                "None \u2192 NaT",
                "pd.NaT",
                "normal",
                "normal",
                "normal",
                "normal",
                "normal",
                "normal",
            ],
        }
    )
    mo.vstack(
        [
            mo.md("### Pandas classic (object dtype)"),
            mo.ui.table(selection=None, data=pdf_classic),
        ]
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Pandas (nullable dtypes)

    `StringDtype` and `Float64` use `pd.NA` as the missing sentinel.

    **Caveat:** pandas converts `float("nan")` to `pd.NA` at storage time in
    nullable `Float64` columns — so NaN and NA are indistinguishable on
    the wire. Both render as `None`.
    """)
    return


@app.cell(hide_code=True)
def _(mo, pd):
    pdf_nullable = pd.DataFrame(
        {
            "string_value": pd.array(
                ["", None, pd.NA, "NULL", "null", " ", "   ", "\t", "\n", "\t \n"],
                dtype="string",
            ),
            "str_description": [
                "empty string",
                "None \u2192 pd.NA",
                "pd.NA",
                "string 'NULL'",
                "string 'null'",
                "single space",
                "three spaces",
                "tab",
                "newline",
                "tab + space + newline",
            ],
            "numeric_value": pd.array(
                [
                    1.0,
                    None,
                    pd.NA,
                    float("nan"),
                    float("inf"),
                    float("-inf"),
                    0.0,
                    42.0,
                    -1.5,
                    100.0,
                ],
                dtype="Float64",
            ),
            "num_description": [
                "1.0",
                "None \u2192 pd.NA",
                "pd.NA",
                "NaN \u2192 pd.NA by pandas",
                "inf",
                "-inf",
                "0.0",
                "42.0",
                "-1.5",
                "100.0",
            ],
        }
    )
    mo.vstack(
        [
            mo.md("### Pandas nullable (StringDtype / Float64)"),
            mo.ui.table(selection=None, data=pdf_nullable),
        ]
    )
    return


if __name__ == "__main__":
    app.run()
