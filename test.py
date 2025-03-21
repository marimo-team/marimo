import marimo

__generated_with = "0.11.19"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    print(mo.raw_cli_args(), mo.cli_args())
    return (mo,)


@app.cell
def _(mo):
    a = mo.ui.number(key="number")
    b = mo.ui.slider(
        1.1, 10.1, 1.0, key="slider", label="test a single slider value: "
    )
    c = mo.ui.range_slider(0, 100, 4, key="range_slider")
    d = mo.ui.checkbox(value=True, key="checkbox")
    e = mo.ui.radio(options=list("def"), value="e", key="radio_tuple")
    f = mo.ui.radio(options={"a": 1, "b": 2, "c": 3}, value="a", key="radio_dict")
    mo.hstack([a, b, c, d, e, f])
    return a, b, c, d, e, f


@app.cell
def _(mo):
    g = mo.ui.text(value="abc", key="text")
    h = mo.ui.text_area(value="abc", key="text")
    i = mo.ui.dropdown(list("abc"), value="b", key="dropdown")
    j = mo.ui.multiselect(list("abc"), value="b", key="multiselect")
    k = mo.ui.file(key="file_single")
    l = mo.ui.file(multiple=True, key="file_multi", kind="area")
    mo.hstack([g, h, i, j, k, l])
    return g, h, i, j, k, l


@app.cell
def _(l):
    for file in l.value:
        print(f"{file.name=}, {file.contents[:100]=}")
    return (file,)


@app.cell
def _(a, b, c, mo):
    data = f"{a.value=}, {b.value=}, {c.value=}"
    mo.download(data.encode(), key="download_str", filename="data_str.txt")
    return (data,)


@app.cell
def _(data, mo):
    mo.download(data.encode, key="download_callable", filename="data_callable.txt")
    return


if __name__ == "__main__":
    app.run()
