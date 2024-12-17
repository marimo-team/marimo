import marimo

__generated_with = "0.9.31"
app = marimo.App(width="medium")


@app.cell
def __(mo, x):
    import datetime

    [
        {
            "a": 1,
            "b": 2.0,
            "c": "foo",
            "d": True,
            "d.1": False,
            "e": mo.ui.slider(0, 10),
            "f": "bar" * 1000,
            "url": "https://www.google.com",
            "g": [1, 2],
            "h": (1, 2),
            "i": {1, 2},
            "j": {"a": 1, "b": 2},
            "none": None,
            "nan": float("nan"),
            "inf": float("inf"),
            "x": x,
            "datetime": datetime.datetime.now(),
            "date": datetime.date.today(),
            "time": datetime.time(1, 2, 3),
        }
    ]
    return (datetime,)


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
