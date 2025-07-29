# Copyright 2025 Marimo. All rights reserved.
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "duckdb==1.3.2",
#     "marimo",
#     "polars==1.31.0",
#     "pyarrow==21.0.0",
#     "sqlglot==27.4.1",
# ]
# ///

# Ignores lack of return type for functions
# ruff: noqa: ANN202
# mypy: disable-error-code="no-untyped-def"

# Ignore SQL Types
# ruff: noqa: F541

import marimo

__generated_with = "0.14.13"
app = marimo.App(width="medium")

with app.setup:
    import argparse
    from datetime import datetime

    import duckdb
    import polars as pl

    import marimo as mo
    from marimo import _loggers

    LOGGER = _loggers.marimo_logger()


@app.cell
def _():
    excluded_keywords = ["__internal", "icu", "has_", "pg_", "allocator"]
    return (excluded_keywords,)


@app.cell(hide_code=True)
def _(excluded_keywords, form, num_keywords, num_types):
    mo.md(
        rf"""
    ## DuckDB Schema

    #### Number of keywords: **{num_keywords}**

    #### Number of types: **{num_types}**

    To update the duckdb codemirror spec, you can either

    -  Run this python script to generate the outputs or
    -  Submit the form below

    {form}

    ❗ And then update the duckdb spec under `frontend/src/core/codemirror/language/languages/sql-dialects/duckdb.ts`

    *Excluded keywords: {excluded_keywords}

    _{mo.md(f"Ran on DuckDB {duckdb.__version__}").right()}_
    _{mo.md(f"Last updated: {datetime.today().date().strftime('%B %d %Y')}").right()}_
    """
    )
    return


@app.cell
def _(df, form):
    parser = argparse.ArgumentParser(
        prog="DuckDB Spec",
        description="Runs SQL to save types and keywords for DuckDB dialect in Codemirror",
    )

    parser.add_argument("-s", "--savepath", default="temp.json")
    args = parser.parse_args()

    if mo.app_meta().mode == "script":
        savepath = args.savepath
        LOGGER.info(f"Saving JSON file to {savepath}")
        write_to_file(df, savepath)
        LOGGER.info(f"Saved file to {savepath}")
    else:
        savepath = form.value
        if savepath is not None and savepath.strip() != "":
            write_to_file(df, savepath)
            mo.output.replace(mo.md(f"## Saved JSON file to {savepath}"))
    return


@app.cell(hide_code=True)
def _():
    _df = mo.sql(
        f"""
        WITH
          duckdb_types_cte AS (
            SELECT
              ROW_NUMBER() OVER () AS rn,
              type_name AS duckdb_types
            FROM
              (
                SELECT DISTINCT
                  type_name
                FROM
                  duckdb_types()
              )
          ),
          duckdb_settings_cte AS (
            SELECT
              ROW_NUMBER() OVER () AS rn,
              name AS duckdb_settings
            FROM
              (
                SELECT DISTINCT
                  name
                FROM
                  duckdb_settings()
              )
          ),
          duckdb_functions_cte AS (
            SELECT
              ROW_NUMBER() OVER () AS rn,
              function_name AS duckdb_functions
            FROM
              (
                SELECT DISTINCT
                  function_name
                FROM
                  duckdb_functions()
              )
          ),
          duckdb_keywords_cte AS (
            SELECT
              ROW_NUMBER() OVER () AS rn,
              keyword_name AS duckdb_keywords
            FROM
              (
                SELECT DISTINCT
                  keyword_name
                FROM
                  duckdb_keywords()
              )
          )
        SELECT
          t.duckdb_types,
          s.duckdb_settings,
          f.duckdb_functions,
          k.duckdb_keywords
        FROM
          duckdb_types_cte AS t
          FULL OUTER JOIN duckdb_settings_cte AS s ON t.rn = s.rn
          FULL OUTER JOIN duckdb_functions_cte AS f ON COALESCE(t.rn, s.rn) = f.rn
          FULL OUTER JOIN duckdb_keywords_cte AS k ON COALESCE(t.rn, s.rn, f.rn) = k.rn
        ORDER BY
          COALESCE(t.rn, s.rn, f.rn, k.rn);
        """
    )
    return


@app.cell(hide_code=True)
def _(excluded_keywords):
    df = mo.sql(
        f"""
        WITH
          stg_keywords AS (
            SELECT
              'duckdb_keywords' AS keyword_group,
              keyword_name AS keyword
            FROM
              duckdb_keywords()
            UNION ALL
            SELECT
              'duckdb_settings' AS keyword_group,
              name AS keyword
            FROM
              duckdb_settings()
            UNION ALL
            SELECT
              'duckdb_functions' AS keyword_group,
              function_name AS keyword
            FROM
              duckdb_functions()
            UNION ALL
            SELECT
              'duckdb_types' AS keyword_group,
              type_name AS keyword
            FROM
              duckdb_types()
          ),
          all_keywords AS (
            SELECT
              STRING_AGG(DISTINCT keyword, ' ' ORDER BY keyword) AS keywords_str
            FROM
              stg_keywords
            WHERE {filter_keywords_query("keyword", excluded_keywords)}
          ),
          builtin_keywords AS (
            SELECT
              STRING_AGG(DISTINCT keyword, ' ' ORDER BY keyword) AS builtin_str
            FROM
              stg_keywords
            WHERE
              keyword_group IN ('duckdb_keywords', 'duckdb_settings')
          ),
          duckdb_types_str AS (
            SELECT
              STRING_AGG(DISTINCT type_name, ' ' ORDER BY type_name) AS types_str
            FROM
              duckdb_types()
          )
        SELECT
          version() as duckdb_version,
          today() as last_updated,
          ak.keywords_str AS keywords,
          bk.builtin_str AS builtin,
          dts.types_str AS types
        FROM
          all_keywords AS ak,
          builtin_keywords AS bk,
          duckdb_types_str AS dts;
        """
    )
    return (df,)


@app.cell
def _(df):
    num_keywords = len(df["keywords"][0].split(" "))
    num_types = len(df["types"][0].split(" "))

    form = mo.ui.text(placeholder="temp.json", label="Savepath").form(
        submit_button_label="Save"
    )
    return form, num_keywords, num_types


@app.function
def filter_keywords_query(column: str, excluded_keywords: list[str]) -> str:
    like_conditions = [
        f"{column} NOT LIKE '{kw}%'" for kw in excluded_keywords
    ]
    where_clause = " AND ".join(like_conditions)
    return where_clause


@app.function
def write_to_file(df: pl.DataFrame, filepath: str) -> None:
    df.select(pl.exclude("builtin")).write_json(filepath)


if __name__ == "__main__":
    app.run()
