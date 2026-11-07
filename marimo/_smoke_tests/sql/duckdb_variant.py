# Copyright 2026 Marimo. All rights reserved.
# From this checkout:
# uv run --with 'duckdb>=1.5' --with pyarrow marimo edit marimo/_smoke_tests/sql/duckdb_variant.py

import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import duckdb

    import marimo as mo
    from marimo._plugins.ui._impl.tables.utils import get_table_manager

    connection = duckdb.connect()
    return connection, duckdb, get_table_manager, mo


@app.cell(hide_code=True)
def _(duckdb, mo):
    mo.md(f"""
    # DuckDB VARIANT: schema and upstream display support

    **DuckDB:** `{duckdb.__version__}` · **marimo:** `{mo.__version__}`

    **Loaded from:** `{mo.__file__}`

    marimo recognizes VARIANT as a heterogeneous type. Its schema should
    retain the native type label and should not emit an unknown-type warning.

    Logical decoding through Arrow/Polars remains upstream work:
    [Arrow Python bindings](https://github.com/apache/arrow/issues/50131)
    and [VARIANT decoder](https://github.com/apache/arrow/pull/50121).
    This notebook does not assert readable VARIANT table output.
    """)
    return


@app.cell
def _(connection):
    examples = connection.sql("""
        SELECT * FROM (VALUES
            (1, {'name': 'Alice', 'age': 30}::VARIANT),
            (2, [1::VARIANT, 'two'::VARIANT]::VARIANT),
            (3, 'héllo 🦆'::VARIANT),
            (4, NULL::VARIANT)
        ) AS examples(id, data)
        ORDER BY id
    """)
    assert examples is not None
    original_types = examples.types
    return examples, original_types


@app.cell
def _(examples, get_table_manager, mo):
    fields = get_table_manager(examples).get_field_types()
    assert fields == [
        ("id", ("integer", "Int32")),
        ("data", ("unknown", "VARIANT")),
    ]
    mo.ui.table(
        [
            {"column": name, "UI type": kind, "native type": native_type}
            for name, (kind, native_type) in fields
        ],
        selection=None,
        show_column_summaries=False,
        label="Schema recognition: heterogeneous values retain the VARIANT label",
    )
    return


@app.cell(hide_code=True)
def _(duckdb, examples, mo):
    try:
        _arrow = examples.to_arrow_table()
    except duckdb.NotImplementedException as error:
        _report = mo.callout(
            f"This DuckDB version cannot export VARIANT to Arrow: {error}",
            kind="info",
        )
    else:
        _report = mo.vstack(
            [
                mo.md("""
                Arrow transports the encoded VARIANT storage below. The binary
                metadata/value fields are expected until upstream decoding is
                available; they are not the logical object shown by DuckDB.
                """),
                mo.plain_text(str(_arrow.schema)),
                mo.plain_text(repr(_arrow.to_pylist())),
            ]
        )
    _report
    return


@app.cell(hide_code=True)
def _(examples, mo):
    mo.vstack(
        [
            mo.md("""
            ## Explicit DuckDB text inspection

            This diagnostic query explicitly casts VARIANT to VARCHAR. It
            demonstrates DuckDB's own text representation, not a marimo decoder.
            The original relation remains native VARIANT.
            """),
            mo.ui.table(
                examples.project("id, data::VARCHAR AS native_text"),
                selection=None,
                show_column_summaries=False,
            ),
        ]
    )
    return


@app.cell
def _(examples, mo, original_types):
    assert examples.types == original_types
    assert examples.filter("id = 1").project(
        "typeof(data), data.age::INTEGER"
    ).fetchall() == [("VARIANT", 30)]
    mo.callout(
        "Native types and SQL field extraction remain intact.", kind="success"
    )
    return


if __name__ == "__main__":
    app.run()
