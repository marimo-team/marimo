# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "pygwalker==0.4.9.13",
#     "vega-datasets==0.9.0",
# ]
# ///
import marimo

__generated_with = "0.9.14"
app = marimo.App(width="medium")


@app.cell
def __():
    import pygwalker as pyg

    from vega_datasets import data
    return data, pyg


@app.cell
def __(data, pyg):
    df = data.iris()

    pyg.walk(df)
    return (df,)


if __name__ == "__main__":
    app.run()
