# Copyright 2025 Marimo. All rights reserved.
"""Test file with SQL parsing errors to test log rules positioning."""

import marimo

__generated_with = "0.8.0"
app = marimo.App()


@app.cell
def __():
    import marimo as mo
    return mo,


@app.cell
def __(mo):
    # This should trigger an MF005 SQL parsing error due to trailing comma
    result = mo.sql(f"""
        WITH ranked_stories AS (
            SELECT
                title,
                score,
                type,
                descendants,
                YEAR(timestamp) AS year,
                MONTH(timestamp) AS month,
                ROW_NUMBER()
                    OVER (PARTITION BY YEAR(timestamp), MONTH(timestamp) ORDER BY score DESC)
                AS rn
            FROM sample_data.hn.hacker_news
            WHERE
                type = 'story'
                AND
                MONTH(timestamp) in (null)
                AND
                descendants NOT NULl

        )

        SELECT
            month,
            score,
            type,
            title,
            hn_url,
            descendants as nb_comments,
            year,
        FROM ranked_stories
        WHERE rn = 1
        ORDER BY year, month;
    """)
    return result,


if __name__ == "__main__":
    app.run()