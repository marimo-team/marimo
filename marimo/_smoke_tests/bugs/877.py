# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.2.12"
app = marimo.App()


@app.cell
def __():
    import altair as alt

    alt.data_transformers.enable("marimo_csv")
    return alt,


if __name__ == "__main__":
    app.run()
