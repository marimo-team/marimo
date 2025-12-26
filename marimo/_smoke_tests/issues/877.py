# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.15.5"
app = marimo.App()


@app.cell
def _():
    import altair as alt

    alt.data_transformers.enable("marimo_csv")
    return


if __name__ == "__main__":
    app.run()
