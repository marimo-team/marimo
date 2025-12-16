import marimo

__generated_with = "0.18.4"
app = marimo.App(width="medium")


@app.cell
def _():
    import altair as alt
    import polars as pl
    import vegafusion

    # Enable VegaFusion data transformer
    alt.data_transformers.enable("vegafusion")

    _df = pl.DataFrame(
        {"category": ["A", "B", "C", "D", "E"], "value": [28, 55, 43, 91, 81]}
    )

    _chart = (
        alt.Chart(_df)
        .mark_bar()
        .encode(
            x=alt.X("category", title="Category"),
            y=alt.Y("value", title="Value"),
            tooltip=["category", "value"],
        )
        .properties(title="Basic VegaFusion Example")
        .interactive()
    )
    _chart
    return


@app.cell
def _():
    import marimo as mo
    return


@app.cell
def _():
    import sys
    return (sys,)


@app.cell
def _(sys):
    sys.stdout.write("Here is a link in stdout: https://marimo.io\n")
    return


@app.cell
def _(sys):
    sys.stderr.write(
        "Here is a link in stderr: https://github.com/marimo-team/marimo\n"
    )
    return


@app.cell
def _():
    print("Here is a link in a print statement: https://docs.marimo.io")
    return


@app.cell
def _(sys):
    sys.stdout.write(
        "Here is a command in stdout: pip install pydantic[openai,google]\n"
    )
    sys.stderr.write("Here is a command in stderr: pip install pandas\n")
    print("Here is a command in a print statement: pip install polars")
    return


@app.cell
def _():
    print("You need to: pip install polars")
    return


@app.cell
def _():
    print("Original functionality: pip install pandas")
    print("Complex package: pip install package[extra,dep]")
    print("Hyphenated package: pip install scikit-learn")

    print("New uv support: uv add polars")
    print("New uv pip support: uv pip install numpy")

    print("Flags before package: pip install -U pandas")
    print("Flags before package (uv): uv add -U polars")
    print("Flags before package (uv pip): uv pip install --upgrade numpy")

    print("Flags after package: uv add polars -U")
    print("Flags after package: pip install pandas --upgrade")
    return


if __name__ == "__main__":
    app.run()
