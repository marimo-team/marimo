import marimo

__generated_with = "0.19.7"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _():
    import argparse

    return (argparse,)


@app.cell
def _(argparse):
    parser = argparse.ArgumentParser(
        description="This notebook shows how to use argparse with marimo",
    )

    parser.add_argument("filename")
    parser.add_argument("-c", "--count", type=int)
    parser.add_argument("-v", "--verbose", action="store_true")
    return (parser,)


@app.cell
def _(mo, parser):
    def parse_args():
        if mo.running_in_notebook():
            # set default values for the command-line arguments when running as a notebook
            filename = "your default value"
            count = 42
            verbose = True
        else:
            args = parser.parse_args()
            filename = args.filename
            count = args.count
            verbose = args.verbose
        return filename, count, verbose

    return (parse_args,)


@app.cell
def _(parse_args):
    print(parse_args())
    return


if __name__ == "__main__":
    app.run()
