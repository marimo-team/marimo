# /// script
# requires-python = ">=3.10"
# dependencies = ["marimo", "pandas"]
# ///

import marimo

__generated_with = "0.24.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import pandas as pd

    return mo, pd


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    # Columns menu: long names

    Open **Columns** in the table below.

    1. Check that long names end in an ellipsis and the type icons remain visible.
    2. Hover over a truncated name to see its full name.
    3. Check that the show-only and eye icons stay aligned for short and long names.
    4. Click an eye icon to hide and restore a column. Click the show-only icon
       to isolate a long-named column, then use **Show all** to restore the table.
    5. Search for `External_ID`, repeat the actions, then clear the search.
    6. Scroll to the bottom of the menu and check the last row's actions.
    """)
    return


@app.cell
def _(mo, pd):
    df = pd.DataFrame(
        {
            "ID": [1, 2, 3],
            "Include_ACT_OS_Analysis": [1, 2, 3],
            "Include_ACT_RFI_Analysis": [1, 2, 3],
            "Include_NoTreat_OS_Analysis": [1, 2, 3],
            "Include_NoTreat_RFI_Analysis": [1, 2, 3],
            "External_ID_matching_normal_sample": ["A", "B", "C"],
            "External_ID_" + "very_long_column_name_" * 8: [1.5, 2.5, 3.5],
            "A long column name with spaces that should remain on one line": [
                True,
                False,
                True,
            ],
            **{
                f"Extra_column_{index:02d}_with_a_long_name_for_scrolling": [
                    1,
                    2,
                    3,
                ]
                for index in range(20)
            },
        }
    )
    mo.ui.table(df, label="Long column names", selection=None)
    return


if __name__ == "__main__":
    app.run()
