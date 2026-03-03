# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "marimo",
#     "simple-parsing==0.1.7",
# ]
# ///

import marimo

__generated_with = "0.19.7"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _():
    import simple_parsing

    return


@app.cell
def _():
    from dataclasses import dataclass
    from simple_parsing import ArgumentParser

    parser = ArgumentParser()
    parser.add_argument("--foo", type=int, default=123, help="foo help")


    @dataclass
    class Options:
        """Help string for this group of command-line arguments."""

        log_dir: str  # Help string for a required str argument
        learning_rate: float = 1e-4  # Help string for a float argument

    parser.add_arguments(Options, dest="options")
    return Options, parser


@app.cell
def _(Options, mo, parser):
    from dataclasses import fields

    def parse_args():
        if mo.running_in_notebook():
            # set default values for the command-line arguments when running as a notebook
            return "foo default", Options("logs/", 1e-4)
        else:
            args = parser.parse_args()
            return args.foo, args.options

    return (parse_args,)


@app.cell
def _(parse_args):
    foo, options = parse_args()
    print(foo, options)
    return


if __name__ == "__main__":
    app.run()
