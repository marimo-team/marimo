import marimo

__generated_with = "0.9.29"
app = marimo.App(width="medium")


@app.cell
def __():
    [
        {
            "a": 1,
            "b": 2.0,
            "c": "foo",
            "d": True,
            "e": False,
        }
    ]
    return


@app.cell
def __():
    class CustomList(list):
        def __init__(self, extra_arg):
            super().__init__((1, 2))


    CustomList(1)
    return (CustomList,)


@app.cell
def __():
    import marimo as mo
    return (mo,)


@app.cell
def __():
    import sys

    # Even though this extends tuple, we preserve the repr
    sys.version_info
    return (sys,)


@app.cell
def __(sys):
    repr(sys.version_info)
    return


@app.cell
def __(sys):
    # Nested, so it is not preserved
    (sys.version_info,)
    return


@app.cell
def __(sys):
    {1, 2, 3, sys.version_info}
    return


@app.cell
def __():
    (1, 2, 3)
    return


@app.cell
def __(mo):
    mo.refs()
    return


@app.cell
def __(mo):
    x = 1
    mo.defs()
    return (x,)


if __name__ == "__main__":
    app.run()
