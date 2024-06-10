# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.6.17"
app = marimo.App(width="medium")


@app.cell
def __():
    import time
    import ibis

    start = time.time()
    df = ibis.read_csv(
        "https://raw.githubusercontent.com/elmoallistair/datasets/main/airlines.csv"
    )
    end = time.time()
    print(f"Time to read csv: {(end - start) * 1000}ms")
    start = time.time()
    from marimo._plugins.ui._impl.tables.utils import get_table_manager_or_none

    print("Columns:", df.__dataframe__().num_columns())
    manager = get_table_manager_or_none(df)
    print("Column types:", manager.get_field_types())
    # Print rows takes much longer
    # print(df.__dataframe__().num_rows())
    end = time.time()
    print(f"Time to read from datatable: {(end - start) * 1000}ms")
    return df, end, get_table_manager_or_none, ibis, manager, start, time


if __name__ == "__main__":
    app.run()
