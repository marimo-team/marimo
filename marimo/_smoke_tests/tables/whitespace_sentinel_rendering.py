# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
#     "pandas",
#     "polars",
# ]
# ///

import marimo

__generated_with = "0.23.1"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    # Whitespace & Sentinel Rendering in Tables

    Tables should visually distinguish sentinel values (null, empty string,
    whitespace-only strings, NaN, ±Infinity, NaT) and strings with
    leading/trailing whitespace from normal data.

    Each framework has its own semantics — this notebook exercises the
    rendering across Polars, Pandas (object dtype), and Pandas nullable
    dtypes, plus a framework-agnostic section for edge-whitespace markers.

    ## Expected rendering
    - `None` / null → muted italic pill labeled `None`
    - Empty string `"\"` → blank in cell, `<empty>` pill in filter dropdown
    - Whitespace-only (` `, `	`, `
    `) → visible markers in a pill
    - Strings with content + leading/trailing whitespace → inline markers on the edges (inner whitespace unchanged)
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


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Strings with edge whitespace

    Distinct from the whitespace-only sentinel above: strings with **content
    plus leading or trailing whitespace** render with inline markers on the
    edges, while inner whitespace is untouched.

    Rendering is frontend-only — backend-agnostic — so these cases use
    plain Python dicts.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    baseline_rows = [
        {"label": "plain", "s": "abc d"},
        {"label": "underscores only (shape ref)", "s": "___abc_d___"},
        {"label": "1 space + underscores", "s": " ___abc_d___ "},
    ]
    mo.vstack(
        [
            mo.md("### Comparison baseline"),
            mo.ui.table(selection=None, data=baseline_rows),
        ]
    )
    return


@app.cell(hide_code=True)
def _(mo):
    supported_rows = [
        {"label": "leading spaces", "s": "      abc d"},
        {"label": "trailing spaces", "s": "abc d    "},
        {"label": "both spaces", "s": " abc d    "},
        {"label": "leading tab", "s": "\tabc d"},
        {"label": "trailing tab", "s": "abc d\t"},
        {"label": "leading newline", "s": "\nabc d"},
        {"label": "trailing newline", "s": "abc d\n"},
        {"label": "carriage return", "s": "\rabc d\r"},
        {"label": "mixed", "s": " \t\nabc d\n\t "},
    ]
    mo.vstack(
        [
            mo.md("### Supported marker chars (space, tab, \\n, \\r)"),
            mo.ui.table(selection=None, data=supported_rows),
        ]
    )
    return


@app.cell(hide_code=True)
def _(mo):
    unicode_rows = [
        {"label": "nbsp (U+00A0)", "s": "\xa0abc d\xa0"},
        {"label": "en space (U+2002)", "s": "\u2002abc d\u2002"},
        {"label": "em space (U+2003)", "s": "\u2003abc d\u2003"},
        {"label": "thin space (U+2009)", "s": "\u2009abc d\u2009"},
        {"label": "ideographic (U+3000)", "s": "\u3000abc d\u3000"},
        {"label": "zero-width (U+200B)", "s": "\u200babc d\u200b"},
        {"label": "BOM (U+FEFF)", "s": "\ufeffabc d\ufeff"},
        {"label": "line sep (U+2028)", "s": "\u2028abc d\u2028"},
        {"label": "para sep (U+2029)", "s": "\u2029abc d\u2029"},
        {"label": "form feed (\\f)", "s": "\fabc d\f"},
        {"label": "vertical tab (\\v)", "s": "\vabc d\v"},
        # Adjacent-escape cases: verify spacing between multi-char \uXXXX markers
        {"label": "3x nbsp adjacent", "s": "\xa0\xa0\xa0abc d\xa0\xa0\xa0"},
        {
            "label": "mixed adjacent (nbsp + en + em)",
            "s": "\xa0\u2002\u2003abc d\u2003\u2002\xa0",
        },
        {"label": "nbsp + regular space", "s": "\xa0 \xa0abc d\xa0 \xa0"},
    ]
    mo.vstack(
        [
            mo.md("### Unicode whitespace — detected by \\s, not in marker table"),
            mo.md(
                "These are detected as whitespace (so they get split from `middle`) but render as the raw char since `WHITESPACE_CHARS` has no mapping — documenting the current gap."
            ),
            mo.ui.table(selection=None, data=unicode_rows),
        ]
    )
    return


@app.cell(hide_code=True)
def _(mo):
    # Strings >= 50 chars collapse into a PopoutColumn (click the row to
    # expand). Expected: the *trigger* shows edge whitespace markers plus
    # the middle text; the *expanded popover* preserves all whitespace via
    # `whitespace-pre-wrap` and the copy icon yields the raw string.
    popout_rows = [
        {
            "label": "long string + edge whitespace (popout)",
            "s": "   "
            + ("The quick brown fox jumps over the lazy dog. " * 2)
            + "   ",
        },
        {
            "label": "long string URL + edge whitespace",
            "s": (
                "  "
                + "https://www.example.com/search?q=the+quick+brown+fox+jumps+over+the+lazy+dog&lang=en&page=1"
                + "   "
            ),
        },
    ]
    mo.vstack(
        [
            mo.md("### Popout column (long strings, ≥ 50 chars)"),
            mo.ui.table(selection=None, data=popout_rows),
        ]
    )
    return


if __name__ == "__main__":
    app.run()
