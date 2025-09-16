import marimo

__generated_with = "0.15.5"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import polars as pl
    import numpy as np
    return (mo,)


@app.cell
def _(mo):
    interactive = mo.ui.checkbox(label="Interactive", value=False)
    interactive
    return (interactive,)


@app.cell
def _(interactive):
    import ibis

    ibis.options.interactive = interactive.value
    f"interactive: {ibis.options.interactive}"
    return (ibis,)


@app.cell
def _(execution_timer, ibis):
    # This should be 200-300ms (lazy)
    with execution_timer("ibis.read_parquet"):
        ibis_table = ibis.read_parquet(
            "s3://gbif-open-data-us-east-1/occurrence/2023-04-01/occurrence.parquet/000000",
        )
    return (ibis_table,)


@app.cell
def _(execution_timer, ibis_table):
    # Takes a while, loads data into memory when `ibis.options.interactive = True`
    with execution_timer("ibis_table"):
        print(ibis_table)
    return


@app.cell
def _(ibis_table):
    # Takes a while, loads data into memory when `ibis.options.interactive = True`
    ibis_table
    return


@app.cell
def _(execution_timer, ibis_table):
    # This should be fast (lazy)
    with execution_timer("t.head(10)"):
        ibis_head = ibis_table.head(10)
    return


@app.cell(hide_code=True)
def _():
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
    return (execution_timer,)


if __name__ == "__main__":
    app.run()
