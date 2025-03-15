import marimo

__generated_with = "0.11.19"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    mo.raw_cli_args()
    return (mo,)


@app.cell
def _(mo):
    b = mo.ui.number(key="number")
    a = mo.ui.slider(1, 10, 1, key="slider")
    c = mo.ui.range_slider(0, 100, 4, key="range_slider")
    mo.hstack([a, b, c])
    return a, b, c


@app.cell
def _(a, b, c):
    print(a.value, b.value, c.value)
    return


@app.cell
def _(mo):
    mo.md("""how to collect all ui's help messages for `python test.py --help`?""")
    return


@app.cell
def _(a, b, c, mo):
    # user-level workaround for cli-driven file saving,
    # would be nice to have this as mo.download(_download_txt, key='download')

    _download_txt = f"{a.value=}, {b.value=}, {c.value=}"
    _key = "download_values"

    if mo.running_in_notebook() or True:
        mo.output.append(
            mo.download(_download_txt, key=_key, filename="download.py")
        )
    else:
        import argparse
        import pathlib

        parser = argparse.ArgumentParser()
        parser.add_argument(
            f"--{_key}", nargs="?", type=pathlib.Path, const="download.txt"
        )
        args = vars(parser.parse_known_args(mo.raw_cli_args())[0])
        if args[_key]:
            with open(args[_key], "w") as _f:
                _f.write(_download_txt)
    return argparse, args, parser, pathlib


if __name__ == "__main__":
    app.run()
