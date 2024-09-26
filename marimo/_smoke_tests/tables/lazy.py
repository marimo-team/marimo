import marimo

__generated_with = "0.8.15"
app = marimo.App(width="medium")


@app.cell
def __():
    import marimo as mo
    import polars as pl
    import numpy as np
    return mo, np, pl


@app.cell
def __(mo):
    mo.md(r"""# Lazy polars""")
    return


@app.cell
def __(execution_timer, np, pl):
    lazy_df = pl.LazyFrame(
        {
            "A": np.random.randint(0, 100, size=100000000),
            "B": np.random.rand(100000000),
        }
    )
    with execution_timer("print(lazy_df)"):
        print(lazy_df)
    lazy_df
    return lazy_df,


@app.cell
def __(lazy_df):
    polars_df = lazy_df.collect()
    polars_df
    return polars_df,


@app.cell
def __(mo):
    mo.md(r"""# Lazy ibis""")
    return


@app.cell
def __():
    import ibis
    return ibis,


@app.cell
def __(execution_timer, ibis):
    # This should be 200-300ms (lazy)
    with execution_timer("ibis.read_parquet"):
        ibis_table = ibis.read_parquet(
            "s3://gbif-open-data-us-east-1/occurrence/2023-04-01/occurrence.parquet/000000",
        )
    return ibis_table,


@app.cell
def __(execution_timer, ibis, ibis_table, mo):
    # This should be slow, needs to load to print
    ibis.options.interactive = False
    with execution_timer("as_html, interactive = False"):
        mo.output.replace(ibis_table)
    return


@app.cell
def __(execution_timer, ibis, ibis_table, mo):
    # This should be slow, needs to load to print
    ibis.options.interactive = True
    with execution_timer("as_html, interactive = True"):
        mo.output.replace(ibis_table)
    ibis.options.interactive = False
    return


@app.cell
def __(execution_timer, ibis_table):
    # This should be fast (lazy)
    with execution_timer("t.head(10)"):
        _private_var = ibis_table.head(10)

    # This should be fast (lazy)
    with execution_timer("t.head(10)"):
        ibis_head = ibis_table.head(10)

    # This should be ~300-500ms
    with execution_timer("t.count().execute()"):
        count = ibis_table.count().execute()
    return count, ibis_head


@app.cell
def __(execution_timer, ibis):
    def time_things(data):
        # This should be fast
        with execution_timer("type"):
            print(type(data))

        from marimo._plugins.ui._impl.tables.utils import get_table_manager

        with execution_timer("get_table_manager"):
            tm = get_table_manager(data)
            print(tm)

        with execution_timer("get_num_rows(force=False)"):
            _res = tm.get_num_rows(force=False)

        with execution_timer("get_num_rows(force=True)"):
            _res = tm.get_num_rows(force=True)

        with execution_timer("get_column_names"):
            _res = tm.get_column_names()

        with execution_timer("get_field_types"):
            _res = tm.get_field_types()

        with execution_timer("take"):
            _res = tm.take(100000, 0)

        with execution_timer("to_sql"):
            if "ibis" in str(type(tm)).lower():
                ibis.to_sql(tm.take(100, 0).take(10, 0).data.count())
    return time_things,


@app.cell
def __(ibis_table, time_things):
    # Ibis
    time_things(ibis_table)
    return


@app.cell
def __(polars_df, time_things):
    # Polars
    time_things(polars_df)
    return


@app.cell
def __(execution_timer, ibis_table, mo):
    # This takes a while (runs a count(*) with no limit)
    with execution_timer("mo.ui.dataframe"):
        _df_viewer = mo.ui.dataframe(ibis_table)
    _df_viewer
    return


@app.cell
def __(execution_timer, ibis_table, mo):
    # This takes a while (runs a count(*) with no limit)
    with execution_timer("mo.ui.dataframe(limit=10)"):
        _df_viewer = mo.ui.dataframe(ibis_table, limit=10)
    _df_viewer
    return


@app.cell(hide_code=True)
def __():
    import time


    class execution_timer:
        def __init__(self, name):
            self.name = name

        def __enter__(self):
            self.start_time = time.time()
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            self.end_time = time.time()
            duration = self.end_time - self.start_time
            if duration < 0.050:  # 50ms
                print(
                    f"\033[92m[FAST]\033[0m {self.name} time: {duration} seconds"
                )
            else:
                print(
                    f"\033[91m[SLOW]\033[0m {self.name} time: {duration} seconds"
                )
    return execution_timer, time


if __name__ == "__main__":
    app.run()
