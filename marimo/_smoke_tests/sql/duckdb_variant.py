# Copyright 2026 Marimo. All rights reserved.
# From this checkout:
# uv run --with 'duckdb>=1.5' --with pyarrow --with pandas marimo edit marimo/_smoke_tests/sql/duckdb_variant.py

import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import duckdb

    import marimo as mo

    connection = duckdb.connect()
    return connection, duckdb, mo


@app.cell(hide_code=True)
def _(duckdb, mo):
    mo.md(f"""
    # Native DuckDB VARIANT display

    **DuckDB:** `{duckdb.__version__}` · **marimo:** `{mo.__version__}`

    **Loaded from:** `{mo.__file__}`

    These tables keep native DuckDB relations. Polars VARIANT decoding is
    an upstream limitation and is not covered by this smoke test.

    Check that objects and lists are readable, Unicode is intact, and the
    first table labels `data` as `VARIANT` instead of exposing binary storage.
    """)
    return


@app.cell
def _(connection):
    examples = connection.sql("""
        SELECT * FROM (VALUES
            (1, 'Object', {'name': 'Alice', 'age': 30}::VARIANT),
            (2, 'Nested object', {'user': {'name': 'Bob'}, 'tags': ['python', 'sql']}::VARIANT),
            (3, 'Mixed list', [1::VARIANT, 'two'::VARIANT, true::VARIANT]::VARIANT),
            (4, 'Unicode', 'héllo 🦆 — 世界'::VARIANT),
            (5, 'Number', 42::VARIANT),
            (6, 'Boolean', true::VARIANT),
            (7, 'SQL NULL', NULL::VARIANT),
            (8, 'String null', 'null'::VARIANT)
        ) AS examples(id, kind, data)
        ORDER BY id
    """)
    assert examples is not None
    original_types = examples.types
    return examples, original_types


@app.cell
def _(examples, mo):
    native_table = mo.ui.table(
        examples,
        selection=None,
        pagination=False,
        show_column_summaries=False,
        label="Native relation: mixed VARIANT values",
    )
    native_table
    return (native_table,)


@app.cell(hide_code=True)
def _(examples, mo):
    mo.vstack(
        [
            mo.md("""
            ## Lazy pagination

            Visit all three pages, then go back. Objects should remain
            readable, and the final page should disable **Next page**.
            """),
            mo.ui.table.lazy(examples, page_size=3, preload=True),
        ]
    )
    return


@app.cell
def _(examples, mo):
    formatted_table = mo.ui.table(
        examples.filter("kind = 'Object'"),
        selection=None,
        show_column_summaries=False,
        format_mapping={
            "data": lambda value: f"{value['name']} (age {value['age']})"
        },
        label="Formatting receives the decoded object: Alice (age 30)",
    )
    formatted_table
    return (formatted_table,)


@app.cell
def _(connection):
    precision = connection.sql("""
        SELECT
            42::VARIANT AS data,
            TIMESTAMP_NS '2026-01-01 12:34:56.123456789' AS stamp,
            INTERVAL '1 month 2 days' AS duration,
            MAP(
                [TIMESTAMP_NS '2026-01-01 00:00:00.000000001',
                 TIMESTAMP_NS '2026-01-01 00:00:00.000000002'],
                ['first', 'second']
            ) AS mapping
    """)
    assert precision is not None
    return (precision,)


@app.cell(hide_code=True)
def _(mo, precision):
    precision_table = mo.ui.table(
        precision, selection=None, show_column_summaries=False
    )
    mo.vstack(
        [
            mo.md("""
            ## Ordinary columns retain their display values

            `stamp` should end in `.123456789`, `duration` should show
            `[1,2,0]`, and expanding `mapping` should show **both** entries
            with distinct nanosecond timestamp keys.
            """),
            precision_table,
        ]
    )
    return (precision_table,)


@app.cell
def _(
    examples,
    formatted_table,
    mo,
    native_table,
    original_types,
    precision,
    precision_table,
):
    assert native_table.data is examples
    assert formatted_table.data.types == original_types
    assert precision_table.data is precision
    assert examples.types == original_types
    assert examples.filter("kind = 'Object'").project(
        "typeof(data), data.age::INTEGER"
    ).fetchall() == [("VARIANT", 30)]
    assert precision.project(
        "stamp::VARCHAR, duration::VARCHAR, cardinality(mapping)"
    ).fetchall() == [("2026-01-01 12:34:56.123456789", "1 month 2 days", 2)]
    mo.callout(
        "Source checks passed: native types, field extraction, nanosecond "
        "precision, interval months, and both map entries remain intact.",
        kind="success",
    )
    return


if __name__ == "__main__":
    app.run()
