# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pandas",
# ]
# ///

import marimo

__generated_with = "0.8.9"
app = marimo.App(width="medium")


@app.cell
def __():
    import pandas as pd

    # Need to set these settings to test if they get us in
    # a bad state
    pd.set_option("display.show_dimensions", "truncate")
    pd.set_option("display.max_rows", None)

    test_data = {
        "date_column": [
            "2015-11-02",
            "2015-11-05",
            "2015-11-06",
            "2015-11-19",
            "2015-11-23",
            "2015-11-27",
            "2015-12-01",
            "2015-12-08",
            "2015-12-09",
            "2015-12-18",
        ],
        "integer_column": [4, 1, 2, 3, 3, 1, 5, 4, 4, 1],
    }

    # Create the DataFrame
    df = pd.DataFrame(test_data)

    # Convert 'date_column' to datetime
    df["date_column"] = pd.to_datetime(df["date_column"])
    df.dtypes
    return df, pd, test_data


if __name__ == "__main__":
    app.run()
